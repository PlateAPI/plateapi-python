import random
import time
from typing import Any, Callable, Dict, Optional

import requests

from ._version import __version__
from .errors import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    PlateAPIError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)

INITIAL_BACKOFF = 1.0
USER_AGENT = "plateapi-python/" + __version__


def parse_retry_after(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


def safe_json(response: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def error_message(body: Optional[Dict[str, Any]], status: int) -> str:
    if body:
        for key in ("detail", "error"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return "Request failed (HTTP %d)" % status


def request_id_of(body: Optional[Dict[str, Any]], response: requests.Response) -> Optional[str]:
    if body and isinstance(body.get("request_id"), str):
        return body["request_id"]
    return response.headers.get("X-Request-ID")


def is_quota_exceeded(body: Optional[Dict[str, Any]]) -> bool:
    if not body:
        return False
    if body.get("code") == "quota_exceeded":
        return True
    detail = body.get("detail")
    return isinstance(detail, str) and detail.lower().startswith("monthly quota exceeded")


class Transport:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        max_wait: Optional[float],
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_wait = max_wait
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })

    def backoff_delay(self, attempt: int) -> float:
        return INITIAL_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)

    def _can_wait(self, seconds: float) -> bool:
        return self.max_wait is None or seconds <= self.max_wait

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        with_key: bool = True,
        max_retries: Optional[int] = None,
    ) -> requests.Response:
        url = self.base_url + path
        # A None header value tells requests to drop the session header for
        # this request only, so health() never touches the shared session.
        headers = None if with_key else {"X-API-Key": None}
        retries = self.max_retries if max_retries is None else max_retries
        attempt = 0

        while True:
            try:
                response = self.session.request(
                    method, url, params=params, headers=headers, timeout=self.timeout,
                )
            except requests.exceptions.Timeout:
                if attempt < retries:
                    self.sleep(self.backoff_delay(attempt))
                    attempt += 1
                    continue
                raise PlateAPIError("Request timed out")
            except requests.exceptions.ConnectionError as e:
                if attempt < retries:
                    self.sleep(self.backoff_delay(attempt))
                    attempt += 1
                    continue
                raise PlateAPIError("Connection failed: %s" % e)

            status = response.status_code
            if status < 400:
                return response

            body = safe_json(response)
            message = error_message(body, status)
            code = body.get("code") if body else None
            if not isinstance(code, str):
                code = None
            common = {
                "status_code": status,
                "code": code,
                "response": response,
                "request_id": request_id_of(body, response),
            }
            retry_after = parse_retry_after(response.headers.get("Retry-After"))

            if status == 429:
                if is_quota_exceeded(body):
                    common["code"] = "quota_exceeded"
                    raise QuotaExceededError(message, retry_after=retry_after, **common)
                wait = retry_after if retry_after is not None else self.backoff_delay(attempt)
                if attempt < retries and self._can_wait(wait):
                    self.sleep(wait)
                    attempt += 1
                    continue
                raise RateLimitError(message, retry_after=retry_after, **common)

            if status >= 500:
                wait = retry_after if retry_after is not None else self.backoff_delay(attempt)
                if attempt < retries and self._can_wait(wait):
                    self.sleep(wait)
                    attempt += 1
                    continue
                raise ServerError(message, retry_after=retry_after, **common)

            if status == 400:
                raise BadRequestError(message, **common)
            if status == 401:
                raise AuthenticationError(message, **common)
            if status == 403:
                raise PermissionDeniedError(message, **common)
            if status == 404:
                raise NotFoundError(message, **common)
            raise PlateAPIError(message, **common)

    def close(self):
        self.session.close()
