# PlateAPI Python SDK

Python SDK for [PlateAPI](https://plateapi.com.au) -- Australian vehicle registration plate lookup.

## Install

```bash
pip install plateapi
```

Requires Python 3.8+.

## Quick start

```python
from plateapi import PlateAPI

client = PlateAPI("pk_live_your_api_key")

result = client.lookup("ABC123", "VIC")
if result.success:
    print(result.vehicle.make)
    print(result.vehicle.model)
    print(result.vehicle.year)
```

## Plate lookup

```python
result = client.lookup("ABC123", "VIC")

print(result.success)                # True if a vehicle was found
print(result.vehicle.make)           # "TOYOTA"
print(result.vehicle.model)          # "HILUX"
print(result.vehicle.year)           # 2015
print(result.vehicle.year_range)     # "2015 - 2023"
print(result.vehicle.lowest_year)    # 2015
print(result.vehicle.highest_year)   # 2023
print(result.vehicle.body)           # "UTILITY"
print(result.vehicle.engine)         # "2.8L"
print(result.vehicle.description)    # "TOYOTA HILUX UTILITY 2.8L"
print(result.duration_ms)            # 2451.3
print(result.source)                 # data source identifier
print(result.request_id)             # "req_7f3a9c1b4e..." (include when contacting support)
```

Valid states: `NSW`, `VIC`, `QLD`, `SA`, `WA`, `TAS`, `NT`, `ACT`.

## Detailed lookup

Pass `detailed=True` to get extended vehicle descriptions when available.

```python
result = client.lookup("ABC123", "NSW", detailed=True)
if result.success:
    print(result.vehicle.detailed_description)
    print(result.vehicle.series)
```

## Multiple matches

Some plates match more than one vehicle record. The best match is in `result.vehicle`, and any alternatives are in `result.alternatives`.

```python
result = client.lookup("ABC123", "VIC")
if result.alternatives:
    for alt in result.alternatives:
        print(f"  Also matched: {alt.make} {alt.model} ({alt.year_range})")
```

## Vehicle database

Browse the full vehicle database (32,000+ vehicles, 213 makes). Each call narrows the cascade -- call with no arguments to get all makes, then pass `make` to get models, and so on. Paid plans only, no quota consumed.

```python
# All makes
makes = client.vehicles()
print(makes[:5])  # ["ABARTH", "AC", "ALFA ROMEO", ...]

# Models for a make
models = client.vehicles(make="TOYOTA")
print(models[:5])  # ["86", "ALPHARD", "AURION", ...]

# Years for a make + model
years = client.vehicles(make="TOYOTA", model="HILUX")

# Full cascade with series and engine
series = client.vehicles(make="TOYOTA", model="HILUX", year=2020)
engines = client.vehicles(make="TOYOTA", model="HILUX", year=2020, series="SR5")
```

## Check usage

```python
usage = client.usage()
print(f"{usage.used}/{usage.limit} lookups used")
print(f"{usage.remaining} remaining")
print(f"Plan: {usage.plan}")
print(f"Period: {usage.period_start} to {usage.period_end}")
print(f"Top-up credits: {usage.topup_credits}")
```

## Request logs

Retrieve your lookup history with optional filtering and pagination. Useful for auditing, debugging, and building analytics.

```python
# Last 10 lookups
logs = client.logs(limit=10)
for entry in logs.logs:
    status = "found" if entry.success else "not found"
    print(f"{entry.created_at} | {entry.plate} ({entry.state}) | {status} | {entry.duration_ms}ms")

print(f"Showing {logs.count} of {logs.total} total")
```

### Filtering

```python
# Filter by plate
logs = client.logs(plate="ABC123")

# Only failed lookups
logs = client.logs(success=False)

# Time range (ISO 8601, UTC)
logs = client.logs(
    since="2026-07-01T00:00:00",
    until="2026-07-31T23:59:59",
)

# Pagination
page1 = client.logs(limit=50, offset=0)
page2 = client.logs(limit=50, offset=50)
```

### Log entry fields

Each `LogEntry` contains: `plate`, `state`, `success` (1 or 0), `error`, `duration_ms`, `make`, `model`, `year`, `client_ip`, `request_id`, `created_at`.

## Health check

Check API availability. No authentication required, no quota consumed.

```python
health = client.health()
print(health.status)  # "ok"
```

## Rate limits

Rate limit info is included with every lookup response.

```python
result = client.lookup("ABC123", "VIC")
print(result.rate_limit.limit)      # monthly lookup allowance
print(result.rate_limit.remaining)   # lookups left this period
print(result.rate_limit.plan)        # current plan slug

# Warn before quota runs out
if result.rate_limit.remaining is not None and result.rate_limit.remaining < 50:
    print(f"Warning: only {result.rate_limit.remaining} lookups remaining")
```

## Error handling

```python
from plateapi import (
    PlateAPI,
    PlateAPIError,
    AuthenticationError,
    RateLimitError,
    QuotaExceededError,
    ServerError,
)

client = PlateAPI("pk_live_your_api_key")

try:
    result = client.lookup("ABC123", "VIC")
except AuthenticationError:
    print("Invalid API key")
except QuotaExceededError:
    print("Monthly quota exceeded -- upgrade at plateapi.com.au")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except ServerError as e:
    print(f"Server error ({e.status_code}), retry after {e.retry_after}s")
except PlateAPIError as e:
    print(f"API error: {e} (status {e.status_code})")
```

## Retry behaviour

The SDK automatically retries on:
- Connection errors
- Timeouts
- 429 rate limit responses (waits for Retry-After header)
- 5xx server errors

Default: 3 retries with exponential backoff and jitter. Configure with:

```python
client = PlateAPI(
    "pk_live_your_api_key",
    max_retries=5,
    timeout=60,
)
```

## Context manager

The SDK uses a `requests.Session` internally. Use a context manager to close it when done.

```python
with PlateAPI("pk_live_your_api_key") as client:
    result = client.lookup("ABC123", "VIC")
    print(result.vehicle.make)
```

Or close manually:

```python
client = PlateAPI("pk_live_your_api_key")
try:
    result = client.lookup("ABC123", "VIC")
finally:
    client.close()
```

## Sandbox

Use plate `TEST123` with any state for testing. Returns a fixed response instantly, no quota consumed.

```python
result = client.lookup("TEST123", "VIC")
assert result.sandbox is True
assert result.success is True
print(result.vehicle.make)  # "TOYOTA"
```

The sandbox also supports `detailed=True`.

## Configuration

```python
client = PlateAPI(
    "pk_live_your_api_key",
    base_url="https://api.plateapi.com.au",  # default
    timeout=30,                               # seconds, default 30
    max_retries=3,                            # default 3
)
```

## Links

- [API Documentation](https://plateapi.com.au/docs)
- [Pricing](https://plateapi.com.au/pricing)
- [Dashboard](https://plateapi.com.au/dashboard)
- [Sign up for free](https://plateapi.com.au/register)
- [Status page](https://plateapi.com.au/status)
- [GitHub](https://github.com/PlateAPI)
