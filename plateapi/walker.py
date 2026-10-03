from typing import Any, Dict, Iterator, Optional, Set

from .types import WalkedVehicle

DEFAULT_WALK_DELAY = 0.15


def walk_vehicles(
    client,
    make: str,
    model: str,
    trims: bool = True,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    engine_contains: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    per_year: bool = False,
    known_ids: Optional[Set[Any]] = None,
    delay: float = DEFAULT_WALK_DELAY,
) -> Iterator[WalkedVehicle]:
    if not isinstance(make, str) or not make.strip():
        raise ValueError("make must be a non-empty string")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    if year_from is not None and year_to is not None and int(year_from) > int(year_to):
        raise ValueError("year_from must not be greater than year_to")
    if delay is not None and delay < 0:
        raise ValueError("delay must not be negative")

    seen = known_ids if known_ids is not None else set()
    needle = engine_contains.upper() if engine_contains else None

    def fetch(**params: Any) -> list:
        result = client.vehicles(vehicle_type=vehicle_type, **params)
        if delay:
            client._transport.sleep(delay)
        return result.data

    if trims:
        models = [
            m for m in fetch(make=make)
            if isinstance(m, str) and (m == model or m.startswith(model + " "))
        ]
    else:
        models = [model]

    for model_name in models:
        for year_value in fetch(make=make, model=model_name):
            try:
                year = int(year_value)
            except (TypeError, ValueError):
                continue
            if year_from is not None and year < int(year_from):
                continue
            if year_to is not None and year > int(year_to):
                continue

            for series in fetch(make=make, model=model_name, year=year):
                for engine in fetch(make=make, model=model_name, year=year, series=series):
                    if needle and needle not in str(engine).upper():
                        continue
                    for variant in fetch(
                        make=make, model=model_name, year=year, series=series, engine=engine,
                    ):
                        records = fetch(
                            make=make, model=model_name, year=year,
                            series=series, engine=engine, variant=variant,
                        )
                        for record in records:
                            if not isinstance(record, dict) or record.get("vehicle_id") is None:
                                continue
                            vehicle_id = record["vehicle_id"]
                            key = (vehicle_id, year) if per_year else vehicle_id
                            if key in seen:
                                continue
                            seen.add(key)
                            yield WalkedVehicle(
                                vehicle_id=vehicle_id,
                                make=make,
                                model=model_name,
                                year=year,
                                series=series,
                                engine=engine,
                                variant=record.get("select_text", variant),
                                description=record.get("description"),
                                long_description=record.get("long_description"),
                                vehicle_type=vehicle_type or "car",
                                raw=record,
                            )
