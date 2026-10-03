"""Every 0.1.0 README snippet still runs unchanged."""
import inspect

import plateapi
from plateapi import (
    AuthenticationError,
    HealthStatus,
    LogEntry,
    LogsResult,
    LookupResult,
    PlateAPI,
    PlateAPIError,
    QuotaExceededError,
    RateLimit,
    RateLimitError,
    ServerError,
    Usage,
    Vehicle,
    VehiclesResult,
)
from plateapi.client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, INITIAL_BACKOFF, MAX_RETRIES, VALID_STATES
from tests.conftest import ok

VEHICLE = {"year_range": "2015 - 2023", "lowest_year": 2015, "highest_year": 2023, "make": "TOYOTA",
           "model": "HILUX", "body": "UTILITY", "engine": "2.8L", "description": "TOYOTA HILUX UTILITY 2.8L"}


def test_010_signatures_unchanged():
    assert list(inspect.signature(PlateAPI.__init__).parameters)[:5] == \
        ["self", "api_key", "base_url", "timeout", "max_retries"]
    assert list(inspect.signature(PlateAPI.lookup).parameters) == ["self", "plate", "state", "detailed"]
    assert list(inspect.signature(PlateAPI.vehicles).parameters)[:7] == \
        ["self", "make", "model", "year", "series", "engine", "variant"]
    assert list(inspect.signature(PlateAPI.logs).parameters) == \
        ["self", "limit", "offset", "since", "until", "plate", "success"]
    assert VALID_STATES == {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}
    assert DEFAULT_BASE_URL == "https://api.plateapi.com.au"
    assert (DEFAULT_TIMEOUT, MAX_RETRIES, INITIAL_BACKOFF) == (30, 3, 1.0)
    for name in ["PlateAPI", "PlateAPIError", "AuthenticationError", "RateLimitError", "QuotaExceededError",
                 "NotFoundError", "ServerError", "Vehicle", "LookupResult", "VehiclesResult", "RateLimit",
                 "Usage", "HealthStatus", "LogEntry", "LogsResult"]:
        assert name in plateapi.__all__


def test_010_dataclass_fields_still_present():
    assert {f for f in Vehicle.__dataclass_fields__} >= {
        "make", "model", "year", "year_range", "lowest_year", "highest_year", "body", "engine",
        "series", "description", "detailed_description"}
    assert {f for f in LookupResult.__dataclass_fields__} >= {
        "success", "vehicle", "alternatives", "source", "duration_ms", "sandbox", "code", "error",
        "request_id", "rate_limit"}
    assert {f for f in VehiclesResult.__dataclass_fields__} == {"success", "type", "data", "total", "duration_ms"}
    assert {f for f in RateLimit.__dataclass_fields__} >= {"limit", "remaining", "plan"}
    assert {f for f in LogEntry.__dataclass_fields__} == {
        "plate", "state", "success", "error", "duration_ms", "make", "model", "year",
        "client_ip", "request_id", "created_at"}
    assert {f for f in LogsResult.__dataclass_fields__} == {"logs", "count", "total", "limit", "offset"}
    assert {f for f in HealthStatus.__dataclass_fields__} == {"status", "version"}
    assert len(Usage.__dataclass_fields__) == 14


def test_010_quick_start_and_alternatives(make_client):
    client, _, _ = make_client([ok({
        "success": True, "vehicle": VEHICLE, "source": "plateapi", "duration_ms": 2451.3,
        "alternatives": [dict(VEHICLE, engine="2.4L")], "request_id": "req_7f3a",
    }, {"X-RateLimit-Limit": "600", "X-RateLimit-Remaining": "500", "X-RateLimit-Plan": "starter"})])
    result = client.lookup("ABC123", "VIC")
    if result.success:
        assert result.vehicle.make == "TOYOTA"
        assert result.vehicle.model == "HILUX"
        assert result.vehicle.year == 2015
        assert result.vehicle.year_range == "2015 - 2023"
        assert result.vehicle.body == "UTILITY"
        assert result.vehicle.description == "TOYOTA HILUX UTILITY 2.8L"
        assert result.duration_ms == 2451.3
        assert result.source == "plateapi"
        assert result.request_id == "req_7f3a"
    if result.alternatives:
        for alt in result.alternatives:
            assert "%s %s (%s)" % (alt.make, alt.model, alt.year_range) == "TOYOTA HILUX (2015 - 2023)"
    assert result.rate_limit.limit == 600
    assert result.rate_limit.remaining is not None and result.rate_limit.remaining < 600
    assert result.rate_limit.plan == "starter"


def test_010_walkdb_style_cascade_loop(make_client):
    """The shape of the customer cascade script: vehicles(**params), .success, .data, dict rows."""
    def level(name, items):
        return ok({"success": True, "data": [{"type": name, "data": items}], "total": len(items)})

    client, _, _ = make_client([
        level("model", ["HILUX", "HILUX SR"]),
        level("year", [2020]),
        level("series", ["GUN126R"]),
        level("engine", ["2.8L"]),
        level("variant", ["4D Ute"]),
        level("vehicle", [{"vehicle_id": 1346446, "select_text": "4D Ute"}]),
        level("year", []),
    ])
    cache = {}

    def cached_vehicles(**params):
        key = tuple(sorted(params.items()))
        if key in cache:
            return cache[key]
        result = client.vehicles(**params)
        if not result.success:
            raise RuntimeError("SDK query reported failure")
        cache[key] = result.data if result.data else []
        return cache[key]

    rows = []
    models = [m for m in cached_vehicles(make="TOYOTA") if m == "HILUX" or m.startswith("HILUX ")]
    for model in models:
        for year in [int(y) for y in cached_vehicles(make="TOYOTA", model=model)]:
            for series in cached_vehicles(make="TOYOTA", model=model, year=year):
                for engine in cached_vehicles(make="TOYOTA", model=model, year=year, series=series):
                    for variant in cached_vehicles(make="TOYOTA", model=model, year=year, series=series, engine=engine):
                        for v in cached_vehicles(make="TOYOTA", model=model, year=year, series=series,
                                                 engine=engine, variant=variant):
                            if isinstance(v, dict) and "vehicle_id" in v:
                                rows.append((v["vehicle_id"], model, year, engine, v.get("select_text", "")))
    client.close()
    assert rows == [(1346446, "HILUX", 2020, "2.8L", "4D Ute")]


def test_010_error_handling_snippet(make_client):
    client, _, _ = make_client([ok({"success": True, "vehicle": VEHICLE})])
    try:
        result = client.lookup("ABC123", "VIC")
    except AuthenticationError:
        raise AssertionError
    except QuotaExceededError:
        raise AssertionError
    except RateLimitError as e:
        raise AssertionError(e.retry_after)
    except ServerError as e:
        raise AssertionError((e.status_code, e.retry_after))
    except PlateAPIError as e:
        raise AssertionError((e, e.status_code))
    assert result.success


def test_010_health_and_context_manager(make_client):
    client, _, _ = make_client([ok({"status": "ok"})])
    with client:
        assert client.health().status == "ok"


def test_010_internals_still_reachable(make_client):
    client, fake, _ = make_client([ok({"status": "ok"})])
    assert client._session is fake
    assert client._request("GET", "/api/v1/health").json() == {"status": "ok"}
    assert client._safe_json(fake.calls and ok({"a": 1})) == {"a": 1}
    assert 1.0 <= client._backoff_delay(0) < 1.5
