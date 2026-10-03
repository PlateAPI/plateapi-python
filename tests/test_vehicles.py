import pytest

from tests.conftest import ok

RECORD = {
    "vehicle_id": 1380801, "vehicle_type": "car", "make": "TOYOTA", "model": "HILUX SR",
    "year_range": "2015-2020", "lowest_year": 2015, "highest_year": 2020,
    "years": [2015, 2016, 2017, 2018, 2019, 2020],
    "description": "15~20 TOYOTA HILUX 2.8L DIESEL", "long_description": "TOYOTA HILUX 10/2015~04/2020",
    "series": "GUN126R -GUN126", "engine": "2.8L,  DIE 1GDFTV I4 16v DOHC I/C Turbo CRD {130kW}",
    "variant": "SR,  4D Ute -, 4WD MR0KA3CD  [THAILAND], AT/MT",
    "body": "UTE", "body_size": None, "doors": 4, "drive": "4WD", "transmission": "AT/MT", "detail": "full",
}


def cascade(level, items):
    return ok({"success": True, "data": [{"type": level, "data": items}], "total": len(items), "duration_ms": 1.0})


def test_vehicles_params_including_empty_series(make_client):
    client, fake, _ = make_client([cascade("engine", ["2.8L"])])
    result = client.vehicles(make="TOYOTA", model="HILUX", year=2020, series="")
    assert fake.calls[0]["url"] == "https://api.plateapi.com.au/api/v1/vehicles"
    assert fake.calls[0]["params"] == {"make": "TOYOTA", "model": "HILUX", "year": "2020", "series": ""}
    assert result.success is True
    assert result.type == "engine"
    assert result.data == ["2.8L"]
    assert result.total == 1
    assert result.vehicle_ids == []


def test_vehicles_makes_level(make_client):
    client, fake, _ = make_client([cascade("make", ["ABARTH", "TOYOTA"])])
    result = client.vehicles()
    assert fake.calls[0]["params"] == {}
    assert result.type == "make"


def test_vehicles_motorcycle_type(make_client):
    client, fake, _ = make_client([cascade("make", ["YAMAHA"])])
    client.vehicles(vehicle_type="motorcycle")
    assert fake.calls[0]["params"] == {"type": "motorcycle"}


def test_vehicles_bad_type_no_request(make_client):
    client, fake, _ = make_client([])
    with pytest.raises(ValueError):
        client.vehicles(vehicle_type="truck")
    assert fake.calls == []


def test_vehicle_level_ids(make_client):
    client, _, _ = make_client([cascade("vehicle", [
        {"vehicle_id": 5434441, "select_text": "a"}, {"vehicle_id": 2573335, "select_text": "b"},
    ])])
    result = client.vehicles(make="KIA", model="SELTOS", year=2022, series="EP81A", engine="2.0L", variant="x")
    assert result.vehicle_ids == [5434441, 2573335]


def test_vehicles_empty_response(make_client):
    client, _, _ = make_client([ok({"success": True, "data": [], "total": 0})])
    result = client.vehicles(make="NOPE")
    assert result.data == [] and result.type is None


def test_vehicle_by_id_fields(make_client):
    client, fake, _ = make_client([ok({"success": True, "vehicle": RECORD, "duration_ms": 2.2})])
    record = client.vehicle_by_id(1380801)
    assert fake.calls[0]["url"] == "https://api.plateapi.com.au/api/v1/vehicles/1380801"
    assert fake.calls[0]["params"] is None
    assert record.vehicle_id == 1380801
    assert record.vehicle_type == "car"
    assert record.model == "HILUX SR"
    assert record.years == [2015, 2016, 2017, 2018, 2019, 2020]
    assert record.series == "GUN126R -GUN126"
    assert record.doors == 4
    assert record.drive == "4WD"
    assert record.transmission == "AT/MT"
    assert record.body_size is None
    assert record.detail == "full"
    assert record.raw is RECORD
    assert "raw" not in repr(record)


def test_vehicle_by_id_digit_string(make_client):
    client, fake, _ = make_client([ok({"success": True, "vehicle": RECORD})])
    client.vehicle_by_id("1380801")
    assert fake.calls[0]["url"].endswith("/vehicles/1380801")


def test_vehicle_by_id_basic_record(make_client):
    basic = dict(RECORD, vehicle_id=7295503, detail="basic", years=[], series=None, variant=None, long_description=None)
    client, _, _ = make_client([ok({"success": True, "vehicle": basic})])
    record = client.vehicle_by_id(7295503)
    assert record.detail == "basic" and record.years == [] and record.series is None


@pytest.mark.parametrize("bad", [True, False, "abc", "", -1, 1.5, None, "12a"])
def test_vehicle_by_id_rejects_bad_input(make_client, bad):
    client, fake, _ = make_client([])
    with pytest.raises(ValueError):
        client.vehicle_by_id(bad)
    assert fake.calls == []
