import pytest
import requests

from plateapi import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    PlateAPIError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from tests.conftest import FakeResponse, ok

FOUND = {"success": True, "vehicle": {"make": "TOYOTA", "vehicle_id": 1}}


@pytest.mark.parametrize("status,cls,body,expected", [
    (400, BadRequestError, {"detail": "Invalid state. Use one of: ACT, NSW"}, "Invalid state. Use one of: ACT, NSW"),
    (401, AuthenticationError, {"detail": "API key has been deactivated"}, "API key has been deactivated"),
    (401, AuthenticationError, None, "Request failed (HTTP 401)"),
    (403, PermissionDeniedError, {"detail": "This API key is not allowed from your IP address."},
     "This API key is not allowed from your IP address."),
    (404, NotFoundError, {"success": False, "code": "not_found", "error": "No vehicle with that vehicle_id."},
     "No vehicle with that vehicle_id."),
    (418, PlateAPIError, {"detail": "teapot"}, "teapot"),
])
def test_4xx_mapping_no_retry(make_client, status, cls, body, expected):
    client, fake, sleeps = make_client([FakeResponse(status, body, {"X-Request-ID": "req_x"})])
    with pytest.raises(cls) as info:
        client.lookup("ABC123", "VIC")
    err = info.value
    assert str(err) == expected
    assert err.status_code == status
    assert err.request_id == "req_x"
    assert len(fake.calls) == 1
    assert sleeps == []


def test_404_carries_code(make_client):
    client, _, _ = make_client([FakeResponse(404, {"success": False, "code": "not_found", "error": "No vehicle with that vehicle_id."})])
    with pytest.raises(NotFoundError) as info:
        client.vehicle_by_id(1)
    assert info.value.code == "not_found"


def test_429_retry_after_is_slept_then_success(make_client):
    client, fake, sleeps = make_client([
        FakeResponse(429, {"detail": "Per-minute rate limit exceeded (10/min on starter plan). Slow down."}, {"Retry-After": "42"}),
        ok(FOUND),
    ])
    assert client.lookup("ABC123", "VIC").success is True
    assert sleeps == [42.0]
    assert len(fake.calls) == 2


def test_429_above_max_wait_raises_immediately(make_client):
    client, fake, sleeps = make_client([
        FakeResponse(429, {"detail": "Vehicle query rate limit exceeded. Try again later."}, {"Retry-After": "61"}),
    ], max_wait=60)
    with pytest.raises(RateLimitError) as info:
        client.vehicles(make="TOYOTA")
    assert info.value.retry_after == 61.0
    assert str(info.value) == "Vehicle query rate limit exceeded. Try again later."
    assert sleeps == []
    assert len(fake.calls) == 1


def test_429_without_retry_after_uses_backoff_then_raises(make_client):
    client, fake, sleeps = make_client([FakeResponse(429, {"detail": "slow down"})] * 4, max_retries=3)
    with pytest.raises(RateLimitError) as info:
        client.lookup("ABC123", "VIC")
    assert info.value.retry_after is None
    assert len(sleeps) == 3
    assert len(fake.calls) == 4


def test_max_wait_none_sleeps_any_length(make_client):
    client, _, sleeps = make_client([
        FakeResponse(429, {"detail": "slow down"}, {"Retry-After": "3600"}),
        ok(FOUND),
    ], max_wait=None)
    assert client.lookup("ABC123", "VIC").success is True
    assert sleeps == [3600.0]


def test_quota_429_raises_at_once(make_client):
    client, fake, sleeps = make_client([
        FakeResponse(429, {"detail": "Monthly quota exceeded. Used 600/600 lookups on starter plan. Upgrade at plateapi.com.au"},
                     {"Retry-After": "3600"}),
    ])
    with pytest.raises(QuotaExceededError) as info:
        client.lookup("ABC123", "VIC")
    err = info.value
    assert isinstance(err, RateLimitError)
    assert err.code == "quota_exceeded"
    assert err.retry_after == 3600.0
    assert str(err).startswith("Monthly quota exceeded")
    assert sleeps == []
    assert len(fake.calls) == 1


def test_quota_by_body_code(make_client):
    client, _, _ = make_client([FakeResponse(429, {"code": "quota_exceeded", "error": "Quota exceeded"})])
    with pytest.raises(QuotaExceededError):
        client.lookup("ABC123", "VIC")


def test_503_lookup_failed_retried_then_server_error(make_client):
    failed = FakeResponse(503, {"success": False, "vehicle": None, "code": "lookup_failed",
                                "error": "Lookup temporarily unavailable. Please retry.", "request_id": "req_lf"})
    client, fake, sleeps = make_client([failed] * 4)
    with pytest.raises(ServerError) as info:
        client.lookup("ABC123", "VIC")
    err = info.value
    assert err.code == "lookup_failed"
    assert err.status_code == 503
    assert err.request_id == "req_lf"
    assert str(err) == "Lookup temporarily unavailable. Please retry."
    assert len(fake.calls) == 4
    assert len(sleeps) == 3


def test_503_retry_after_is_slept(make_client):
    client, _, sleeps = make_client([
        FakeResponse(503, {"success": False, "code": "unavailable", "data": [], "total": 0}, {"Retry-After": "5"}),
        ok({"success": True, "data": [{"type": "make", "data": ["TOYOTA"]}], "total": 1}),
    ])
    assert client.vehicles().data == ["TOYOTA"]
    assert sleeps == [5.0]


def test_502_html_body(make_client):
    client, _, _ = make_client([FakeResponse(502, None, text="<html>bad gateway</html>")] * 4)
    with pytest.raises(ServerError) as info:
        client.lookup("ABC123", "VIC")
    assert str(info.value) == "Request failed (HTTP 502)"
    assert info.value.code is None


def test_junk_retry_after_counts_as_absent(make_client):
    client, _, sleeps = make_client([
        FakeResponse(429, {"detail": "slow"}, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        ok(FOUND),
    ])
    client.lookup("ABC123", "VIC")
    assert len(sleeps) == 1 and 1.0 <= sleeps[0] < 2.0


def test_connection_error_retried_then_raised(make_client):
    client, fake, sleeps = make_client([
        requests.exceptions.ConnectionError("refused"),
        requests.exceptions.ConnectTimeout("slow"),
        ok(FOUND),
    ])
    assert client.lookup("ABC123", "VIC").success is True
    assert len(sleeps) == 2

    client, fake, sleeps = make_client([requests.exceptions.ConnectionError("refused")] * 4)
    with pytest.raises(PlateAPIError) as info:
        client.lookup("ABC123", "VIC")
    assert str(info.value).startswith("Connection failed")
    assert len(fake.calls) == 4


def test_timeout_message(make_client):
    client, _, _ = make_client([requests.exceptions.ReadTimeout("slow")], max_retries=0)
    with pytest.raises(PlateAPIError) as info:
        client.lookup("ABC123", "VIC")
    assert str(info.value) == "Request timed out"
