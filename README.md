# PlateAPI Python SDK

Python SDK for [PlateAPI](https://plateapi.com.au) -- Australian vehicle registration plate lookup
and the PlateAPI vehicle database.

## Install

```bash
pip install plateapi
```

Requires Python 3.8+ and `requests`. No other dependencies.

## Quick start

```python
from plateapi import PlateAPI

client = PlateAPI("pk_live_your_api_key")

result = client.lookup("ABC123", "VIC")
if result.success:
    print(result.vehicle.make, result.vehicle.model, result.vehicle.year_range)
    print(result.vehicle.vehicle_id)   # PlateAPI's stable ID for this variant
    print(result.match)                # "exact", "multiple" or "ambiguous"
```

Get a free API key (20 lookups a month, no card) at [plateapi.com.au/register](https://plateapi.com.au/register/).
Full API reference: [plateapi.com.au/docs](https://plateapi.com.au/docs/).

## Plate lookup

```python
result = client.lookup("ABC123", "VIC")

result.success                    # True when a vehicle was found
result.match                      # "exact" | "multiple" | "ambiguous" (None when not found)
result.vehicle.make               # "TOYOTA"
result.vehicle.model              # "HILUX"
result.vehicle.year_range         # "2015-2020" ("2020-ON" for models still in production)
result.vehicle.lowest_year        # 2015
result.vehicle.highest_year       # 2020 (None for an open range)
result.vehicle.year               # same as lowest_year
result.vehicle.body               # "UTE" (may be None)
result.vehicle.engine             # "2.8L" (may be None)
result.vehicle.description        # "15~20 TOYOTA HILUX 2.8L DIESEL"
result.vehicle.vehicle_id         # 1380801 (None when the variant is not certain)
result.alternatives               # other candidate variants, same fields, each with its own vehicle_id
result.candidate_ids              # every non-null vehicle_id, primary first: [1380801]
result.request_id                 # "req_7f3a9c1b4e8d2f6a0c5e" -- quote this when contacting support
result.duration_ms                # 1509.96
result.sandbox                    # True only for the TEST123 sandbox plate
```

Valid states: `NSW`, `VIC`, `QLD`, `SA`, `WA`, `TAS`, `NT`, `ACT`. Plate and state are
upper-cased and trimmed for you; an unknown state raises `ValueError` before any request.

### Not found

A plate that does not resolve is a normal result, not an exception. It is still HTTP 200 and it
still counts against your monthly quota (typos are common, so validate input first).

```python
result = client.lookup("ZZZ999", "NSW")
if not result.success:
    print(result.code)    # "not_found"
    print(result.error)   # human-readable message
```

### `vehicle_id` and `match`

Every vehicle in a lookup carries `vehicle_id`: PlateAPI's ID for the exact variant. It is stable
(the same variant always returns the same ID) and it is the same ID the vehicle database uses, so
you can link your own records (products, SKUs, fitment rows) to it. It is `None` when the variant
could not be identified with certainty; an ID is never guessed.

`match` tells you how to read the result:

| `match` | Meaning | What to store |
|---------|---------|---------------|
| `exact` | one variant | `result.vehicle.vehicle_id` |
| `multiple` | several trims of one make and model, all on sale at the same time; `vehicle` is the first with its ID, the rest are in `alternatives` | all of `result.candidate_ids`, or let the customer pick |
| `ambiguous` | candidates are different makes or models, or different generations; `vehicle.vehicle_id` is `None` and `alternatives` lists every candidate (including the one shown as `vehicle`) with its ID | `result.candidate_ids` (a picker is best) |

```python
result = client.lookup("ABC123", "VIC")
if result.match == "exact":
    save(result.vehicle.vehicle_id)
else:
    for alt in result.alternatives:
        print(alt.vehicle_id, alt.description, alt.year_range)
    save_all(result.candidate_ids)
```

With `match: "multiple"` the primary `vehicle_id` identifies the first candidate, not necessarily
the plate's own trim. Lookup text (`make`, `model`, `description`) can be worded differently from
the record the ID points to: integrate on `vehicle_id`, not on text.

### Detailed lookup

```python
result = client.lookup("ABC123", "NSW", detailed=True)
print(result.vehicle.detailed_description)
# "TOYOTA HILUX SR Auto or Manual AN120 AN130 05/2015~12/2020 4 Door UTE 4x4 DIESEL 2.8 litre, ..."
```

`detailed_description` may be `None` for some vehicles even when requested.

### Rate limit headers

Each lookup result carries the quota headers from the response:

```python
result.rate_limit.limit            # monthly lookup allowance
result.rate_limit.remaining        # lookups left this period
result.rate_limit.plan             # "starter"
result.rate_limit.topup_remaining  # remaining top-up credits, only while they are being consumed
```

## Vehicle database

Starter plans and above. The database holds 23,000+ Australian-market car variants (225+ makes)
and 15,000+ motorcycles, scooters and ATVs (420+ makes). Queries do not consume lookup quota; they
have their own limit of 500 requests per minute.

### Cascade

`vehicles()` returns one level of the seven-level cascade. Each call narrows it: no arguments gives
the makes, `make` gives models, and so on down to full vehicle records with a `vehicle_id`.

```python
r = client.vehicles()                                   # r.type == "make"
r.data[:3]                                              # ["ABARTH", "ACE EV", "ACURA"]

r = client.vehicles(make="TOYOTA")                      # "model"
r = client.vehicles(make="TOYOTA", model="HILUX")       # "year"  (newest first)
r = client.vehicles(make="TOYOTA", model="HILUX", year=2019)                    # "series"
r = client.vehicles(make="TOYOTA", model="HILUX", year=2019,
                    series="GUN126R -GUN126")                                    # "engine"
r = client.vehicles(make="TOYOTA", model="HILUX", year=2019,
                    series="GUN126R -GUN126",
                    engine="2.8L,  DIE 1GDFTV I4 16v DOHC I/C Turbo CRD {130kW}")  # "variant"
r = client.vehicles(make="TOYOTA", model="HILUX", year=2019,
                    series="GUN126R -GUN126",
                    engine="2.8L,  DIE 1GDFTV I4 16v DOHC I/C Turbo CRD {130kW}",
                    variant="4D Ute -, 4WD MR0HA3CD  [THAILAND], AT/MT")          # "vehicle"
r.data           # [{"vehicle_id": 1346446, "select_text": "...", "description": "...", "long_description": "..."}]
r.vehicle_ids    # [1346446]
```

`VehiclesResult` fields: `success`, `type` (the level returned), `data` (list of strings, ints for
years, or dicts at the vehicle level), `total`, `duration_ms`, plus the `vehicle_ids` property.

Rules worth knowing:

- Pass each value exactly as the previous level returned it. Values contain commas, double spaces,
  braces and brackets, and matching is case-sensitive. The SDK URL-encodes them for you.
- An empty-string series is a real value. Pass `series=""` to continue below it.
- Unknown values are not errors: you get `success == True` with an empty `data` list. A `503`
  (database briefly unavailable) is retried by the SDK and then raised as `ServerError`.
- Trims are filed as separate models (`HILUX`, `HILUX SR`, `HILUX SR5 EXTRA CAB`), so to cover a
  base model walk every model name that starts with it. `walk_vehicles()` below does this.
- The vehicle level is a list: a few paths return two records whose catalogue entries overlap in
  that year. Use each record's description and `vehicle_by_id()` to tell them apart.
- `vehicle_id` identifies the variant, not the year: a variant returns the same ID under every
  model year it was sold.

### Motorcycles

Motorcycles have their own cascade. Pass `vehicle_type="motorcycle"` on every level
(`"car"` is the default).

```python
r = client.vehicles(vehicle_type="motorcycle")                       # 420+ makes
r = client.vehicles(make="YAMAHA", model="MT-07", vehicle_type="motorcycle")
```

A motorcycle plate lookup returns the same ID as the motorcycle cascade. Any other `vehicle_type`
raises `ValueError`.

### One vehicle by ID

```python
record = client.vehicle_by_id(1380801)   # also accepts "1380801"

record.vehicle_id        # 1380801
record.vehicle_type      # "car" or "motorcycle"
record.make              # "TOYOTA"
record.model             # "HILUX SR"
record.year_range        # "2015-2020"
record.lowest_year       # 2015
record.highest_year      # 2020 (None for an open range)
record.years             # [2015, 2016, 2017, 2018, 2019, 2020]
record.description       # "15~20 TOYOTA HILUX 2.8L DIESEL"
record.long_description  # "TOYOTA HILUX 10/2015~04/2020"
record.series            # "GUN126R -GUN126"
record.engine            # "2.8L,  DIE 1GDFTV I4 16v DOHC I/C Turbo CRD {130kW}"
record.variant           # "SR,  4D Ute -, 4WD MR0KA3CD  [THAILAND], AT/MT"
record.body              # "UTE"
record.body_size         # "COMPACT" / "MEDIUM" / "FULL-SIZE" for SUVs, else None
record.doors             # 4
record.drive             # "4WD", "AWD", "RWD", "FWD", "6X4", ...
record.transmission      # "AT", "MT", "AT/MT", "CVT", "DCT", "AMT"
record.detail            # "full" or "basic"
record.raw               # the vehicle dict exactly as returned
```

- `detail == "basic"` means the vehicle has an ID but its full record has not been added yet:
  `series`, `variant` and `long_description` are `None` and `years` is empty. The ID does not
  change when the full record is added.
- `body`, `body_size`, `doors`, `drive` and `transmission` are read from the variant name and are
  `None` when it does not carry them.
- A retired ID that was merged into another returns the current record, so `record.vehicle_id` can
  differ from the ID you asked for. Compare them if you care.
- An unknown ID raises `NotFoundError` (code `not_found`). Anything that is not a non-negative
  integer or a string of digits raises `ValueError` before any request.
- The sandbox plate `TEST123` returns `vehicle_id` 1380801, a real record, so you can test this
  call without using quota.

## Walking the cascade

`walk_vehicles()` collects every `vehicle_id` for one make and model: it walks models, years,
series, engines, variants and vehicles for you and yields each vehicle the first time it is seen.
This is how you map existing fitment text (make, model, years, engine) to PlateAPI IDs once.

```python
for v in client.walk_vehicles("TOYOTA", "HILUX", year_from=2015, year_to=2020, engine_contains="2.8L"):
    print(v.vehicle_id, v.model, v.year, v.series, v.engine, v.variant)
```

| Argument | Default | Meaning |
|----------|---------|---------|
| `make`, `model` | required | base model; must be non-empty |
| `trims` | `True` | also walk every model name starting with `model + " "` (`HILUX SR`, `HILUX SR5 EXTRA CAB`). `False` walks `model` only and skips the models request |
| `year_from`, `year_to` | `None` | inclusive model-year window; `ValueError` if from > to |
| `engine_contains` | `None` | only engines whose name contains this text (case-insensitive), e.g. `"2.8L"` or `"DIE"` |
| `vehicle_type` | `None` | `"motorcycle"` for the motorcycle cascade |
| `per_year` | `False` | yield one row per vehicle per model year instead of one row per vehicle (for year-level master lists) |
| `known_ids` | `None` | a set of IDs already handled; they are not yielded again and the set is updated in place (resume an interrupted walk) |
| `delay` | `0.15` | seconds to pause after each request; the default stays under 500 requests/minute |

Each `WalkedVehicle` has `vehicle_id`, `make`, `model` (the exact model name it was found under),
`year`, `series`, `engine`, `variant` (the cascade's `select_text`), `description`,
`long_description`, `vehicle_type` and `raw` (the vehicle dict). The path fields are where the
vehicle was first seen; with `per_year=True` you get a row for every year.

The walk is a generator, so results arrive as they are found and you can stop at any time. Errors
are raised at the point they happen; everything already yielded stays with you. A `429` whose
`Retry-After` is longer than `max_wait` (60 s by default) raises `RateLimitError` immediately
rather than sleeping, so a long walk never sits silently. Catch it, save your progress and resume
later with `known_ids`.

A Hilux walk (all trims, all years) is about 350 requests and takes a minute or two at the default
delay; a single make and model with a year window is usually a few seconds.

### Example: stream IDs to a CSV, resumable

```python
import csv
import os
from plateapi import PlateAPI, RateLimitError

FILENAME = "hilux.csv"
FIELDS = ["vehicle_id", "make", "model", "year", "series", "engine", "variant", "description"]

known = set()
if os.path.exists(FILENAME):
    with open(FILENAME, newline="", encoding="utf-8") as f:
        known = {int(row["vehicle_id"]) for row in csv.DictReader(f)}

with PlateAPI(os.environ["PLATEAPI_KEY"]) as client, \
        open(FILENAME, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    if not known:
        writer.writeheader()
    try:
        for v in client.walk_vehicles("TOYOTA", "HILUX", known_ids=known):
            writer.writerow({k: getattr(v, k) for k in FIELDS})
            f.flush()
    except RateLimitError as e:
        print("rate limited, retry in %s s; %d rows saved" % (e.retry_after, len(known)))
```

Run it again later and it continues where it stopped.

### Linking products (SKUs) to vehicles

Keep a many-to-many table `(sku, vehicle_id)`. Walk the cascade once per fitment line to fill it,
then on each plate lookup query the table by `result.vehicle.vehicle_id` (or every ID in
`result.candidate_ids` when `match` is `multiple`). Store IDs, not text. The full guide is at
[plateapi.com.au/docs/vehicles](https://plateapi.com.au/docs/vehicles/#vehicles-skus).

## Account

### Usage

```python
usage = client.usage()
usage.plan               # "starter"
usage.monthly_limit      # 600
usage.used_this_month    # 12
usage.remaining          # 588
usage.percent_used       # 2.0
usage.rate_limit_per_min # 10
usage.period_start       # "2026-09-07 00:00:00" (UTC)
usage.period_end         # None when there is no billing period (free plan)
usage.days_remaining     # None when there is no billing period
usage.last_lookup_at     # "2026-10-03 03:20:02"
usage.topup_credits      # remaining purchased top-up lookups
usage.cancel_at_period_end, usage.cancel_at
```

### Lookup history

```python
logs = client.logs(limit=50, offset=0, since="2026-10-01T00:00:00", until=None, plate=None, success=None)
for entry in logs.logs:
    print(entry.created_at, entry.plate, entry.state, entry.success, entry.duration_ms, entry.request_id)
print(logs.count, "of", logs.total)
```

`limit` is at most 500. `since` / `until` are ISO 8601 UTC. `success=True` / `False` filters
found / not found. `LogEntry` fields: `plate`, `state`, `success` (1 or 0), `error`,
`duration_ms`, `make`, `model`, `year`, `client_ip`, `request_id`, `created_at`.

### Health

```python
client.health().status   # "ok"
```

No key is sent, no quota is used, and the call makes a single attempt.

## Sandbox

Plate `TEST123` with any state returns a fixed vehicle instantly: free, no quota, no rate limit.
A valid key is still required. Use it in integration tests and CI.

```python
result = client.lookup("TEST123", "VIC")
result.sandbox              # True
result.vehicle.vehicle_id   # 1380801
client.vehicle_by_id(result.vehicle.vehicle_id).model   # "HILUX SR"
```

## Errors

All errors are subclasses of `PlateAPIError` and carry `status_code`, `code` (the API's machine
code when it sent one), `request_id` and the raw `response`. Messages are the API's own.

| Exception | HTTP | When |
|-----------|------|------|
| `BadRequestError` | 400 | invalid plate, state, cascade parameter or vehicle ID |
| `AuthenticationError` | 401 | missing, invalid or deactivated key; email not verified |
| `PermissionDeniedError` | 403 | IP not on the key's allowlist, account banned, or vehicle database on a Free / Lite plan |
| `NotFoundError` | 404 | `vehicle_by_id()` with an unknown ID |
| `RateLimitError` | 429 | per-minute limit; `retry_after` in seconds |
| `QuotaExceededError` | 429 | monthly quota used up (subclass of `RateLimitError`; `retry_after` is 3600) |
| `ServerError` | 5xx | after retries; `code` is `lookup_failed` or `unavailable` when the API sent one, `retry_after` when it sent a header |
| `PlateAPIError` | other | connection failures, timeouts, unexpected statuses |

```python
from plateapi import (
    PlateAPI, PlateAPIError, AuthenticationError, PermissionDeniedError,
    RateLimitError, QuotaExceededError, NotFoundError, ServerError,
)

try:
    result = client.lookup("ABC123", "VIC")
except QuotaExceededError as e:
    print("monthly quota used up:", e)
except RateLimitError as e:
    print("slow down, retry in", e.retry_after, "seconds")
except AuthenticationError as e:
    print("key problem:", e)
except ServerError as e:
    print("temporary failure, not billed:", e.code, e.request_id)
except PlateAPIError as e:
    print("error", e.status_code, e)
```

A lookup that cannot be completed (`503`, code `lookup_failed`) is never billed; retry it after a
few seconds. A `200` with `code: "internal_error"` is also not billed and is retried by the SDK
before it is returned.

## Retries and waiting

| Response | Behaviour |
|----------|-----------|
| connection error, timeout | retried up to `max_retries` with backoff (1 s, 2 s, 4 s plus jitter), then `PlateAPIError` |
| 400 / 401 / 403 / 404 | raised at once, no retry |
| 429 monthly quota | `QuotaExceededError` at once, no sleep |
| 429 other | sleeps `Retry-After` (backoff if absent) and retries; if `Retry-After` is longer than `max_wait` or retries are used up, `RateLimitError` |
| 5xx | same rule, then `ServerError` |
| 200 lookup with `internal_error` | retried with backoff, then returned |

```python
client = PlateAPI(
    "pk_live_your_api_key",
    base_url="https://api.plateapi.com.au",  # default
    timeout=30,          # seconds per request
    max_retries=3,       # retries after the first attempt
    max_wait=60.0,       # longest Retry-After to sleep; None waits any length
)
```

Every request sends `User-Agent: plateapi-python/<version>`.

## Context manager

The client holds a `requests.Session`. Close it when you are done:

```python
with PlateAPI("pk_live_your_api_key") as client:
    result = client.lookup("ABC123", "VIC")
```

or call `client.close()`.

## Upgrading from 0.1.0

Everything written against 0.1.0 keeps working: no public name, signature, default, field or
exception was removed. New in 0.2.0: `vehicle_id`, `match`, `candidate_ids`, `vehicle_by_id()`,
`walk_vehicles()`, `vehicle_type="motorcycle"`, `vehicle_ids`, `topup_remaining`,
`BadRequestError`, `PermissionDeniedError`, `request_id` on errors, `max_wait`, type hints.

Behaviour changes to be aware of:

- A monthly-quota `429` now raises `QuotaExceededError` immediately. 0.1.0 slept for an hour and
  retried. `QuotaExceededError` is now a subclass of `RateLimitError`, so `except RateLimitError`
  catches both, as it effectively did before.
- A `Retry-After` longer than `max_wait` (60 s) raises instead of sleeping. Pass `max_wait=None`
  for the old behaviour.
- `health()` makes one attempt and no longer touches the shared session's headers.
- Error messages are the API's `detail` / `error` text instead of fixed strings.
- 400, 403 and 404 raise `BadRequestError`, `PermissionDeniedError` and `NotFoundError` (all
  subclasses of `PlateAPIError`, which 0.1.0 raised).

See [CHANGELOG.md](CHANGELOG.md).

## Links

- [API documentation](https://plateapi.com.au/docs/)
- [Vehicle database and vehicle IDs](https://plateapi.com.au/docs/vehicles/)
- [OpenAPI spec](https://plateapi.com.au/openapi.json)
- [Pricing](https://plateapi.com.au/pricing/)
- [Dashboard](https://plateapi.com.au/dashboard/)
- [Status page](https://plateapi.com.au/status/)
- [Support](mailto:support@plateapi.com.au)
