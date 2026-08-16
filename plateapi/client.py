import time
import random
from typing import Optional, List, Dict, Any

import requests

from .errors import (
    PlateAPIError,
    AuthenticationError,
    RateLimitError,
    QuotaExceededError,
    NotFoundError,
    ServerError,
)
from .types import Vehicle, RateLimit, LookupResult, Usage, HealthStatus, LogEntry, LogsResult

VALID_STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}
DEFAULT_BASE_URL = "https://api.plateapi.com.au"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def _parse_vehicle(data: dict) -> Vehicle:
    if not data:
        return None
    return Vehicle(
        make=data.get("make"),
        model=data.get("model"),
        year=data.get("lowest_year"),
        year_range=data.get("year_range"),
        lowest_year=data.get("lowest_year"),
        highest_year=data.get("highest_year"),
        body=data.get("body"),
        engine=data.get("engine"),
        series=data.get("series"),
        description=data.get("description"),
        detailed_description=data.get("detailed_description"),
    )


def _parse_rate_limit(headers: dict) -> RateLimit:
    raw_limit = headers.get("X-RateLimit-Limit")
    raw_remaining = headers.get("X-RateLimit-Remaining")
    return RateLimit(
        limit=int(raw_limit) if raw_limit and raw_limit != "unlimited" else None,
        remaining=int(raw_remaining) if raw_remaining and raw_remaining != "unlimited" else None,
        plan=headers.get("X-RateLimit-Plan"),
    )


class PlateAPI:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, params: dict = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.request(
                    method, url, params=params, timeout=self.timeout,
                )
            except requests.exceptions.Timeout:
                last_error = PlateAPIError("Request timed out")
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise last_error
            except requests.exceptions.ConnectionError as e:
                last_error = PlateAPIError(f"Connection failed: {e}")
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise last_error

            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid API key",
                    status_code=401,
                    response=response,
                )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                body = self._safe_json(response)
                code = body.get("code", "") if body else ""
                if code == "quota_exceeded":
                    raise QuotaExceededError(
                        "Monthly quota exceeded",
                        status_code=429,
                        code=code,
                        response=response,
                    )
                if attempt < self.max_retries:
                    wait = float(retry_after) if retry_after else self._backoff_delay(attempt)
                    time.sleep(wait)
                    continue
                raise RateLimitError(
                    "Rate limit exceeded",
                    retry_after=float(retry_after) if retry_after else None,
                    status_code=429,
                    response=response,
                )

            if response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                if attempt < self.max_retries:
                    wait = float(retry_after) if retry_after else self._backoff_delay(attempt)
                    time.sleep(wait)
                    continue
                raise ServerError(
                    f"Server error ({response.status_code})",
                    retry_after=float(retry_after) if retry_after else None,
                    status_code=response.status_code,
                    response=response,
                )

            if response.status_code >= 400:
                body = self._safe_json(response)
                message = "Request failed"
                if body:
                    message = body.get("detail", body.get("error", message))
                raise PlateAPIError(
                    message,
                    status_code=response.status_code,
                    response=response,
                )

            return response

        raise last_error or PlateAPIError("Request failed after retries")

    def _backoff_delay(self, attempt: int) -> float:
        return INITIAL_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)

    def _backoff(self, attempt: int):
        time.sleep(self._backoff_delay(attempt))

    def _safe_json(self, response: requests.Response) -> Optional[dict]:
        try:
            return response.json()
        except (ValueError, KeyError):
            return None

    def lookup(
        self,
        plate: str,
        state: str,
        detailed: bool = False,
    ) -> LookupResult:
        state = state.upper().strip()
        plate = plate.upper().strip()

        if state not in VALID_STATES:
            raise ValueError(f"Invalid state '{state}'. Must be one of: {', '.join(sorted(VALID_STATES))}")

        if not plate:
            raise ValueError("Plate cannot be empty")

        params = {"plate": plate, "state": state}
        if detailed:
            params["detailed"] = "true"

        response = self._request("GET", "/api/v1/lookup", params=params)
        body = response.json()
        rate_limit = _parse_rate_limit(response.headers)

        vehicle = _parse_vehicle(body.get("vehicle"))
        alternatives = [_parse_vehicle(a) for a in body.get("alternatives", []) if a]

        return LookupResult(
            success=body.get("success", False),
            vehicle=vehicle,
            alternatives=alternatives,
            source=body.get("source"),
            duration_ms=body.get("duration_ms"),
            sandbox=body.get("sandbox", False),
            code=body.get("code"),
            error=body.get("error"),
            request_id=body.get("request_id"),
            rate_limit=rate_limit,
        )

    def vehicles(
        self,
        make: str = None,
        model: str = None,
        year: int = None,
        series: str = None,
        engine: str = None,
    ) -> List[str]:
        params = {}
        if make:
            params["make"] = make
        if model:
            params["model"] = model
        if year:
            params["year"] = str(year)
        if series:
            params["series"] = series
        if engine:
            params["engine"] = engine

        response = self._request("GET", "/api/v1/vehicles", params=params)
        return response.json()

    def usage(self) -> Usage:
        response = self._request("GET", "/api/v1/keys/usage")
        body = response.json()
        return Usage(
            used=body.get("used", 0),
            limit=body.get("limit", 0),
            remaining=body.get("remaining", 0),
            plan=body.get("plan"),
            period_start=body.get("period_start"),
            period_end=body.get("period_end"),
            topup_credits=body.get("topup_credits", 0),
        )

    def logs(
        self,
        limit: int = 100,
        offset: int = 0,
        since: str = None,
        until: str = None,
        plate: str = None,
        success: bool = None,
    ) -> LogsResult:
        params = {"limit": str(limit), "offset": str(offset)}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if plate:
            params["plate"] = plate
        if success is not None:
            params["success"] = str(success).lower()

        response = self._request("GET", "/api/v1/keys/logs", params=params)
        body = response.json()

        entries = []
        for entry in body.get("logs", []):
            entries.append(LogEntry(
                plate=entry.get("plate"),
                state=entry.get("state"),
                success=entry.get("success", 0),
                error=entry.get("error"),
                duration_ms=entry.get("duration_ms"),
                make=entry.get("make"),
                model=entry.get("model"),
                year=entry.get("year"),
                client_ip=entry.get("client_ip"),
                request_id=entry.get("request_id"),
                created_at=entry.get("created_at"),
            ))

        return LogsResult(
            logs=entries,
            count=body.get("count", 0),
            total=body.get("total", 0),
            limit=body.get("limit", limit),
            offset=body.get("offset", offset),
        )

    def health(self) -> HealthStatus:
        old_headers = dict(self._session.headers)
        self._session.headers.pop("X-API-Key", None)
        try:
            response = self._request("GET", "/api/v1/health")
            body = response.json()
            return HealthStatus(
                status=body.get("status", "unknown"),
                version=body.get("version"),
            )
        finally:
            self._session.headers.update(old_headers)

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
