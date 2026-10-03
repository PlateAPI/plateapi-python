import pytest

from plateapi import RateLimitError, WalkedVehicle
from tests.conftest import FakeResponse, ok


def level(name, items):
    return ok({"success": True, "data": [{"type": name, "data": items}], "total": len(items)})


def vehicle(vehicle_id, text="4D Ute"):
    return {"vehicle_id": vehicle_id, "select_text": text,
            "description": "desc %d" % vehicle_id, "long_description": "long %d" % vehicle_id}


def hilux_responses(trims=True):
    responses = []
    if trims:
        responses.append(level("model", ["HILUX", "HILUX SR", "HILUXX", "CAMRY"]))
    # HILUX: years 2020, 2019 -> one series -> one engine -> one variant -> same ID both years
    responses += [
        level("year", [2020, 2019]),
        level("series", ["GUN126R"]),
        level("engine", ["2.8L DIE"]),
        level("variant", ["4D Ute"]),
        level("vehicle", [vehicle(100)]),
        level("series", ["GUN126R"]),
        level("engine", ["2.8L DIE"]),
        level("variant", ["4D Ute"]),
        level("vehicle", [vehicle(100)]),
    ]
    if trims:
        # HILUX SR: one year, empty-string series, two engines
        responses += [
            level("year", [2019]),
            level("series", [""]),
            level("engine", ["2.8L DIE", "2.4L DIE"]),
            level("variant", ["SR 4D Ute"]),
            level("vehicle", [vehicle(200, "SR 4D Ute"), vehicle(201, "SR 4D Ute")]),
            level("variant", ["SR 4D Ute"]),
            level("vehicle", [vehicle(300, "SR 4D Ute")]),
        ]
    return responses


def test_walk_with_trims_dedupes_across_years(make_client):
    client, fake, sleeps = make_client(hilux_responses())
    found = list(client.walk_vehicles("TOYOTA", "HILUX"))

    assert [v.vehicle_id for v in found] == [100, 200, 201, 300]
    first = found[0]
    assert isinstance(first, WalkedVehicle)
    assert (first.make, first.model, first.year, first.series, first.engine, first.variant) == \
        ("TOYOTA", "HILUX", 2020, "GUN126R", "2.8L DIE", "4D Ute")
    assert first.description == "desc 100" and first.long_description == "long 100"
    assert first.vehicle_type == "car"
    assert first.raw == vehicle(100)
    assert found[1].model == "HILUX SR" and found[1].series == ""
    assert found[3].engine == "2.4L DIE"

    assert fake.calls[0]["params"] == {"make": "TOYOTA"}
    assert fake.calls[7]["params"] == {"make": "TOYOTA", "model": "HILUX", "year": "2019", "series": "GUN126R"}
    assert "series" not in fake.calls[11]["params"]
    assert fake.calls[12]["params"]["series"] == ""
    assert len(fake.calls) == len(hilux_responses())
    assert sleeps == [0.15] * len(fake.calls)


def test_walk_without_trims_skips_models_request(make_client):
    client, fake, _ = make_client(hilux_responses(trims=False))
    found = list(client.walk_vehicles("TOYOTA", "HILUX", trims=False))
    assert [v.vehicle_id for v in found] == [100]
    assert fake.calls[0]["params"] == {"make": "TOYOTA", "model": "HILUX"}


def test_walk_year_range_and_engine_filter(make_client):
    client, fake, _ = make_client([
        level("year", [2021, 2020, 2019]),
        level("series", ["S"]),
        level("engine", ["2.8L DIE", "2.4L DIE"]),
        level("variant", ["V"]),
        level("vehicle", [vehicle(1)]),
    ])
    found = list(client.walk_vehicles(
        "TOYOTA", "HILUX", trims=False, year_from=2020, year_to=2020, engine_contains="2.8l",
    ))
    assert [v.vehicle_id for v in found] == [1]
    years_requested = [c["params"].get("year") for c in fake.calls[1:]]
    assert set(years_requested) == {"2020"}
    assert fake.calls[3]["params"]["engine"] == "2.8L DIE"


def test_walk_per_year_yields_one_row_per_year(make_client):
    client, _, _ = make_client(hilux_responses(trims=False))
    found = list(client.walk_vehicles("TOYOTA", "HILUX", trims=False, per_year=True))
    assert [(v.vehicle_id, v.year) for v in found] == [(100, 2020), (100, 2019)]


def test_walk_known_ids_resume(make_client):
    client, _, _ = make_client(hilux_responses())
    known = {100, 200}
    found = list(client.walk_vehicles("TOYOTA", "HILUX", known_ids=known))
    assert [v.vehicle_id for v in found] == [201, 300]
    assert known == {100, 200, 201, 300}


def test_walk_passes_type_on_every_request(make_client):
    client, fake, _ = make_client([
        level("model", ["MT-07"]),
        level("year", [2022]),
        level("series", ["RM33"]),
        level("engine", ["0.7L"]),
        level("variant", ["MT-07"]),
        level("vehicle", [vehicle(7076553, "MT-07")]),
    ])
    found = list(client.walk_vehicles("YAMAHA", "MT-07", vehicle_type="motorcycle"))
    assert found[0].vehicle_type == "motorcycle"
    assert all(c["params"]["type"] == "motorcycle" for c in fake.calls)


def test_walk_delay_zero_does_not_sleep(make_client):
    client, _, sleeps = make_client(hilux_responses(trims=False))
    list(client.walk_vehicles("TOYOTA", "HILUX", trims=False, delay=0))
    assert sleeps == []


def test_walk_429_mid_walk_raises_after_earlier_yields(make_client):
    responses = hilux_responses(trims=False)
    responses[5] = FakeResponse(429, {"detail": "Vehicle query rate limit exceeded. Try again later."},
                                {"Retry-After": "7200"})
    client, _, _ = make_client(responses)
    found = []
    with pytest.raises(RateLimitError) as info:
        for v in client.walk_vehicles("TOYOTA", "HILUX", trims=False):
            found.append(v.vehicle_id)
    assert found == [100]
    assert info.value.retry_after == 7200.0


@pytest.mark.parametrize("make,model,kwargs", [
    ("", "HILUX", {}),
    ("TOYOTA", " ", {}),
    (None, "HILUX", {}),
    ("TOYOTA", "HILUX", {"year_from": 2020, "year_to": 2019}),
    ("TOYOTA", "HILUX", {"delay": -1}),
    ("TOYOTA", "HILUX", {"vehicle_type": "bus"}),
])
def test_walk_validation_makes_no_request(make_client, make, model, kwargs):
    client, fake, _ = make_client([])
    with pytest.raises(ValueError):
        list(client.walk_vehicles(make, model, **kwargs))
    assert fake.calls == []
