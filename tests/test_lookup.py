import pytest

from plateapi import LookupResult, PlateAPI, Vehicle
from tests.conftest import FakeResponse, ok

HILUX = {
    "year_range": "2015-2020", "lowest_year": 2015, "highest_year": 2020,
    "make": "TOYOTA", "model": "HILUX", "description": "15~20 TOYOTA HILUX 2.8L DIESEL",
    "body": "UTE", "engine": "2.8L", "vehicle_id": 1380801,
}
COROLLA_A = {
    "year_range": "2003-2006", "lowest_year": 2003, "highest_year": 2006,
    "make": "TOYOTA", "model": "COROLLA", "description": "03~06 TOYOTA COROLLA SPORTIVO 1.8L PETROL",
    "body": "HATCHBACK", "engine": "1.8L", "vehicle_id": 5152708,
}
COROLLA_B = dict(COROLLA_A, description="03~06 TOYOTA COROLLA ASCENT 1.8L PETROL", body="SEDAN", vehicle_id=1857621)


def test_exact_lookup(make_client):
    client, fake, _ = make_client([ok({
        "success": True, "vehicle": HILUX, "alternatives": [], "match": "exact",
        "source": "plateapi", "duration_ms": 1509.9, "request_id": "req_abc",
    }, {"X-RateLimit-Limit": "600", "X-RateLimit-Remaining": "599", "X-RateLimit-Plan": "starter"})])

    result = client.lookup("abc 123", "vic")

    call = fake.calls[0]
    assert call["url"] == "https://api.plateapi.com.au/api/v1/lookup"
    assert call["params"] == {"plate": "ABC 123", "state": "VIC"}
    assert fake.headers["X-API-Key"] == "pk_live_test"
    assert fake.headers["User-Agent"].startswith("plateapi-python/")
    assert result.success is True
    assert result.match == "exact"
    assert result.vehicle.vehicle_id == 1380801
    assert result.vehicle.year == 2015
    assert result.vehicle.make == "TOYOTA"
    assert result.candidate_ids == [1380801]
    assert result.request_id == "req_abc"
    assert result.rate_limit.limit == 600
    assert result.rate_limit.remaining == 599
    assert result.rate_limit.plan == "starter"
    assert result.rate_limit.topup_remaining is None


def test_multiple_candidate_ids_in_order_without_duplicates(make_client):
    client, _, _ = make_client([ok({
        "success": True, "vehicle": COROLLA_A, "match": "multiple",
        "alternatives": [COROLLA_B, COROLLA_A],
    })])
    result = client.lookup("ABC123", "VIC")
    assert result.match == "multiple"
    assert result.candidate_ids == [5152708, 1857621]
    assert [a.vehicle_id for a in result.alternatives] == [1857621, 5152708]


def test_ambiguous_primary_has_no_id(make_client):
    primary = dict(COROLLA_A, vehicle_id=None)
    client, _, _ = make_client([ok({
        "success": True, "vehicle": primary, "match": "ambiguous",
        "alternatives": [COROLLA_A, HILUX],
    })])
    result = client.lookup("ABC123", "VIC")
    assert result.match == "ambiguous"
    assert result.vehicle.vehicle_id is None
    assert result.candidate_ids == [5152708, 1380801]


def test_not_found_is_a_normal_result(make_client):
    client, _, _ = make_client([ok({
        "success": False, "vehicle": None, "code": "not_found",
        "error": "No vehicle found", "request_id": "req_nf",
    })])
    result = client.lookup("ZZZ999", "NSW")
    assert result.success is False
    assert result.code == "not_found"
    assert result.vehicle is None
    assert result.candidate_ids == []
    assert result.match is None
    assert result.request_id == "req_nf"


def test_sandbox_and_detailed(make_client):
    client, fake, _ = make_client([ok({
        "success": True, "sandbox": True, "match": "exact",
        "vehicle": dict(HILUX, detailed_description="TOYOTA HILUX SR ... {130kW}"),
    })])
    result = client.lookup("TEST123", "VIC", detailed=True)
    assert fake.calls[0]["params"]["detailed"] == "true"
    assert result.sandbox is True
    assert result.vehicle.detailed_description.startswith("TOYOTA HILUX SR")


def test_request_id_falls_back_to_header(make_client):
    client, _, _ = make_client([ok({"success": True, "vehicle": HILUX}, {"X-Request-ID": "req_hdr"})])
    assert client.lookup("ABC123", "VIC").request_id == "req_hdr"


def test_topup_remaining_header(make_client):
    client, _, _ = make_client([ok({"success": True, "vehicle": HILUX}, {"X-Topup-Remaining": "412"})])
    assert client.lookup("ABC123", "VIC").rate_limit.topup_remaining == 412


def test_unlimited_rate_limit_headers_are_none(make_client):
    client, _, _ = make_client([ok({"success": True, "vehicle": HILUX},
                                   {"X-RateLimit-Limit": "unlimited", "X-RateLimit-Remaining": "unlimited"})])
    rl = client.lookup("ABC123", "VIC").rate_limit
    assert rl.limit is None and rl.remaining is None


def test_internal_error_is_retried_then_returned(make_client):
    internal = {"success": False, "vehicle": None, "code": "internal_error", "error": "internal_error: X"}
    client, fake, sleeps = make_client([ok(internal), ok({"success": True, "vehicle": HILUX})])
    result = client.lookup("ABC123", "VIC")
    assert result.success is True
    assert len(fake.calls) == 2
    assert len(sleeps) == 1


def test_internal_error_every_time_is_returned(make_client):
    internal = {"success": False, "vehicle": None, "code": "internal_error", "error": "internal_error: X"}
    client, fake, sleeps = make_client([ok(internal)] * 4)
    result = client.lookup("ABC123", "VIC")
    assert result.success is False
    assert result.code == "internal_error"
    assert len(fake.calls) == 4
    assert len(sleeps) == 3


def test_invalid_state_and_empty_plate(make_client):
    client, fake, _ = make_client([])
    with pytest.raises(ValueError):
        client.lookup("ABC123", "XX")
    with pytest.raises(ValueError):
        client.lookup("   ", "VIC")
    assert fake.calls == []


def test_candidate_ids_on_a_bare_result():
    result = LookupResult(vehicle=Vehicle(vehicle_id=5), alternatives=[Vehicle(vehicle_id=None), Vehicle(vehicle_id=7)])
    assert result.candidate_ids == [5, 7]


def test_empty_api_key_rejected():
    with pytest.raises(ValueError):
        PlateAPI("")
