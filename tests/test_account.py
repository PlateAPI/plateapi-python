import pytest

from plateapi import PlateAPI
from tests.conftest import FakeResponse, ok


def test_usage(make_client):
    client, fake, _ = make_client([ok({
        "email": "a@b.c", "plan": "starter", "monthly_limit": 600, "used_this_month": 12,
        "remaining": 588, "percent_used": 2.0, "rate_limit_per_min": 10,
        "last_lookup_at": "2026-10-03 03:20:02", "period_start": "2026-09-07 00:00:00",
        "period_end": None, "days_remaining": None, "cancel_at_period_end": False,
        "cancel_at": None, "topup_credits": 500,
    })])
    usage = client.usage()
    assert fake.calls[0]["url"].endswith("/api/v1/keys/usage")
    assert usage.plan == "starter"
    assert usage.remaining == 588
    assert usage.period_end is None
    assert usage.topup_credits == 500


def test_logs_params_and_parsing(make_client):
    client, fake, _ = make_client([ok({
        "logs": [{"plate": "ABC123", "state": "VIC", "success": 1, "error": None, "duration_ms": 1900.5,
                  "make": "TOYOTA", "model": "HILUX", "year": 2015, "client_ip": "1.2.3.4",
                  "request_id": "req_1", "created_at": "2026-10-03 03:00:00"}],
        "count": 1, "total": 40, "limit": 10, "offset": 20,
    })])
    logs = client.logs(limit=10, offset=20, since="2026-10-01T00:00:00", plate="ABC123", success=True)
    assert fake.calls[0]["params"] == {
        "limit": "10", "offset": "20", "since": "2026-10-01T00:00:00", "plate": "ABC123", "success": "true",
    }
    assert logs.total == 40 and logs.count == 1 and logs.offset == 20
    entry = logs.logs[0]
    assert entry.plate == "ABC123" and entry.success == 1 and entry.request_id == "req_1"


def test_health_sends_no_key_and_leaves_session_alone(make_client):
    client, fake, _ = make_client([ok({"status": "ok"})])
    health = client.health()
    assert health.status == "ok"
    call = fake.calls[0]
    assert call["headers"] == {"X-API-Key": None}
    assert fake.headers["X-API-Key"] == "pk_live_test"


def test_health_single_attempt(make_client):
    client, fake, sleeps = make_client([FakeResponse(503, None, text="down")])
    with pytest.raises(Exception):
        client.health()
    assert len(fake.calls) == 1
    assert sleeps == []


def test_context_manager_closes_session(make_client):
    client, fake, _ = make_client([])
    with client as c:
        assert c is client
    assert fake.closed is True


def test_health_header_override_really_drops_key():
    # Real requests.Session: a None header value removes the session header for that request.
    import requests
    from requests import Request
    session = requests.Session()
    session.headers["X-API-Key"] = "pk_live_test"
    prepared = session.prepare_request(Request("GET", "https://example.invalid/", headers={"X-API-Key": None}))
    assert "X-API-Key" not in prepared.headers
    assert session.headers["X-API-Key"] == "pk_live_test"
