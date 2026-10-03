from typing import Any, Dict, Iterator, Optional, Set

import requests

from ._http import Transport, safe_json
from .types import (
    HealthStatus,
    LogEntry,
    LogsResult,
    LookupResult,
    RateLimit,
    Usage,
    Vehicle,
    VehicleRecord,
    VehiclesResult,
    WalkedVehicle,
)
from .walker import DEFAULT_WALK_DELAY, walk_vehicles as _walk_vehicles

VALID_STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}
VALID_VEHICLE_TYPES = {"car", "motorcycle"}
DEFAULT_BASE_URL = "https://api.plateapi.com.au"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
DEFAULT_MAX_WAIT = 60.0
INITIAL_BACKOFF = 1.0


def _parse_vehicle(data: Optional[dict]) -> Optional[Vehicle]:
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
        vehicle_id=data.get("vehicle_id"),
    )


def _header_int(headers, name: str) -> Optional[int]:
    raw = headers.get(name)
    if raw is None or raw == "unlimited":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_rate_limit(headers) -> RateLimit:
    return RateLimit(
        limit=_header_int(headers, "X-RateLimit-Limit"),
        remaining=_header_int(headers, "X-RateLimit-Remaining"),
        plan=headers.get("X-RateLimit-Plan"),
        topup_remaining=_header_int(headers, "X-Topup-Remaining"),
    )


def _parse_record(data: dict) -> VehicleRecord:
    return VehicleRecord(
        vehicle_id=data.get("vehicle_id"),
        vehicle_type=data.get("vehicle_type"),
        make=data.get("make"),
        model=data.get("model"),
        year_range=data.get("year_range"),
        lowest_year=data.get("lowest_year"),
        highest_year=data.get("highest_year"),
        years=list(data.get("years") or []),
        description=data.get("description"),
        long_description=data.get("long_description"),
        series=data.get("series"),
        engine=data.get("engine"),
        variant=data.get("variant"),
        body=data.get("body"),
        body_size=data.get("body_size"),
        doors=data.get("doors"),
        drive=data.get("drive"),
        transmission=data.get("transmission"),
        detail=data.get("detail"),
        raw=data,
    )


class PlateAPI:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        max_wait: Optional[float] = DEFAULT_MAX_WAIT,
    ):
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key must be a non-empty string")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_wait = max_wait
        self._transport = Transport(
            api_key=api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_wait=max_wait,
        )

    # Kept for scripts that reached into 0.1.0 internals.
    @property
    def _session(self) -> requests.Session:
        return self._transport.session

    def _request(self, method: str, path: str, params: Optional[dict] = None) -> requests.Response:
        return self._transport.request(method, path, params=params)

    def _backoff_delay(self, attempt: int) -> float:
        return self._transport.backoff_delay(attempt)

    def _backoff(self, attempt: int):
        self._transport.sleep(self._transport.backoff_delay(attempt))

    def _safe_json(self, response: requests.Response) -> Optional[dict]:
        return safe_json(response)

    # ---- lookups ----

    def lookup(self, plate: str, state: str, detailed: bool = False) -> LookupResult:
        state = state.upper().strip()
        plate = plate.upper().strip()

        if state not in VALID_STATES:
            raise ValueError(
                "Invalid state '%s'. Must be one of: %s" % (state, ", ".join(sorted(VALID_STATES)))
            )
        if not plate:
            raise ValueError("Plate cannot be empty")

        params = {"plate": plate, "state": state}
        if detailed:
            params["detailed"] = "true"

        attempt = 0
        while True:
            response = self._transport.request("GET", "/api/v1/lookup", params=params)
            body = response.json()
            # internal_error is a 200 that is not billed; one more try usually succeeds.
            if (
                body.get("success") is False
                and body.get("code") == "internal_error"
                and attempt < self.max_retries
            ):
                self._transport.sleep(self._transport.backoff_delay(attempt))
                attempt += 1
                continue
            break

        return LookupResult(
            success=body.get("success", False),
            vehicle=_parse_vehicle(body.get("vehicle")),
            alternatives=[_parse_vehicle(a) for a in body.get("alternatives", []) if a],
            source=body.get("source"),
            duration_ms=body.get("duration_ms"),
            sandbox=body.get("sandbox", False),
            code=body.get("code"),
            error=body.get("error"),
            request_id=body.get("request_id") or response.headers.get("X-Request-ID"),
            rate_limit=_parse_rate_limit(response.headers),
            match=body.get("match"),
        )

    # ---- vehicle database ----

    def vehicles(
        self,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[int] = None,
        series: Optional[str] = None,
        engine: Optional[str] = None,
        variant: Optional[str] = None,
        *,
        vehicle_type: Optional[str] = None,
    ) -> VehiclesResult:
        if vehicle_type is not None and vehicle_type not in VALID_VEHICLE_TYPES:
            raise ValueError(
                "Invalid vehicle_type '%s'. Must be one of: %s"
                % (vehicle_type, ", ".join(sorted(VALID_VEHICLE_TYPES)))
            )

        params: Dict[str, str] = {}
        if vehicle_type is not None:
            params["type"] = vehicle_type
        if make is not None:
            params["make"] = make
        if model is not None:
            params["model"] = model
        if year is not None:
            params["year"] = str(year)
        if series is not None:
            params["series"] = series
        if engine is not None:
            params["engine"] = engine
        if variant is not None:
            params["variant"] = variant

        response = self._transport.request("GET", "/api/v1/vehicles", params=params)
        body = response.json()
        data_list = body.get("data", [])
        first = data_list[0] if data_list and isinstance(data_list[0], dict) else {}
        return VehiclesResult(
            success=body.get("success", False),
            type=first.get("type"),
            data=first.get("data", []),
            total=body.get("total", 0),
            duration_ms=body.get("duration_ms"),
        )

    def vehicle_by_id(self, vehicle_id) -> VehicleRecord:
        if isinstance(vehicle_id, bool):
            raise ValueError("vehicle_id must be an integer")
        if isinstance(vehicle_id, str):
            if not vehicle_id.isdigit():
                raise ValueError("vehicle_id must be an integer")
            vehicle_id = int(vehicle_id)
        elif not isinstance(vehicle_id, int) or vehicle_id < 0:
            raise ValueError("vehicle_id must be an integer")

        response = self._transport.request("GET", "/api/v1/vehicles/%d" % vehicle_id)
        body = response.json()
        return _parse_record(body.get("vehicle") or {})

    def walk_vehicles(
        self,
        make: str,
        model: str,
        *,
        trims: bool = True,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        engine_contains: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        per_year: bool = False,
        known_ids: Optional[Set[Any]] = None,
        delay: float = DEFAULT_WALK_DELAY,
    ) -> Iterator[WalkedVehicle]:
        return _walk_vehicles(
            self, make, model,
            trims=trims, year_from=year_from, year_to=year_to,
            engine_contains=engine_contains, vehicle_type=vehicle_type,
            per_year=per_year, known_ids=known_ids, delay=delay,
        )

    # ---- account ----

    def usage(self) -> Usage:
        response = self._transport.request("GET", "/api/v1/keys/usage")
        body = response.json()
        return Usage(
            email=body.get("email"),
            plan=body.get("plan"),
            monthly_limit=body.get("monthly_limit", 0),
            used_this_month=body.get("used_this_month", 0),
            remaining=body.get("remaining", 0),
            percent_used=body.get("percent_used"),
            rate_limit_per_min=body.get("rate_limit_per_min", 0),
            last_lookup_at=body.get("last_lookup_at"),
            period_start=body.get("period_start"),
            period_end=body.get("period_end"),
            days_remaining=body.get("days_remaining"),
            cancel_at_period_end=body.get("cancel_at_period_end", False),
            cancel_at=body.get("cancel_at"),
            topup_credits=body.get("topup_credits", 0),
        )

    def logs(
        self,
        limit: int = 100,
        offset: int = 0,
        since: Optional[str] = None,
        until: Optional[str] = None,
        plate: Optional[str] = None,
        success: Optional[bool] = None,
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

        response = self._transport.request("GET", "/api/v1/keys/logs", params=params)
        body = response.json()

        entries = [
            LogEntry(
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
            )
            for entry in body.get("logs", [])
        ]

        return LogsResult(
            logs=entries,
            count=body.get("count", 0),
            total=body.get("total", 0),
            limit=body.get("limit", limit),
            offset=body.get("offset", offset),
        )

    def health(self) -> HealthStatus:
        response = self._transport.request("GET", "/api/v1/health", with_key=False, max_retries=0)
        body = response.json()
        return HealthStatus(
            status=body.get("status", "unknown"),
            version=body.get("version"),
        )

    # ---- lifecycle ----

    def close(self):
        self._transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
