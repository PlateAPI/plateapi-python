# PlateAPI Python SDK

Python SDK for [PlateAPI](https://plateapi.com.au) -- Australian vehicle registration plate lookup.

## Install

```bash
pip install plateapi
```

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

## Detailed lookup

```python
result = client.lookup("ABC123", "NSW", detailed=True)
if result.success:
    print(result.vehicle.detailed_description)
    print(result.vehicle.engine)
    print(result.vehicle.body)
```

## Check usage

```python
usage = client.usage()
print(f"{usage.used}/{usage.limit} lookups used")
print(f"{usage.remaining} remaining")
print(f"Plan: {usage.plan}")
```

## Vehicle database

```python
makes = client.vehicles()
models = client.vehicles(make="TOYOTA")
years = client.vehicles(make="TOYOTA", model="HILUX")
```

## Health check

```python
health = client.health()
print(health.status)
```

## Rate limits

Rate limit info is returned with every lookup:

```python
result = client.lookup("ABC123", "VIC")
print(result.rate_limit.remaining)
print(result.rate_limit.plan)
```

## Error handling

```python
from plateapi import (
    PlateAPI,
    AuthenticationError,
    RateLimitError,
    QuotaExceededError,
)

client = PlateAPI("pk_live_your_api_key")

try:
    result = client.lookup("ABC123", "VIC")
except AuthenticationError:
    print("Invalid API key")
except QuotaExceededError:
    print("Monthly quota exceeded")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
```

## Retry behaviour

The SDK automatically retries on:
- Connection errors
- Timeouts
- 429 rate limit responses (waits for Retry-After)
- 5xx server errors

Default: 3 retries with exponential backoff and jitter. Configure with:

```python
client = PlateAPI("pk_live_your_api_key", max_retries=5, timeout=60)
```

## Context manager

```python
with PlateAPI("pk_live_your_api_key") as client:
    result = client.lookup("ABC123", "VIC")
```

## Sandbox

Use plate `TEST123` with any state for testing. No quota consumed.

```python
result = client.lookup("TEST123", "VIC")
assert result.sandbox is True
```

## Links

- [API Documentation](https://plateapi.com.au/docs)
- [Dashboard](https://plateapi.com.au/dashboard)
- [Sign up for free](https://plateapi.com.au/register)
