# Changelog

## 0.2.0 -- 2026-10-03

Every 0.1.0 program keeps working. New fields and methods only; see "Upgrading from 0.1.0"
in the README for the few behaviour changes.

### Added

- `Vehicle.vehicle_id`: PlateAPI's stable ID for the exact variant, on the primary vehicle and
  on every entry in `alternatives`.
- `LookupResult.match` (`exact`, `multiple`, `ambiguous`) and `LookupResult.candidate_ids`.
- `PlateAPI.vehicle_by_id(vehicle_id)` -> `VehicleRecord` for `GET /api/v1/vehicles/{vehicle_id}`.
- `PlateAPI.vehicles(..., vehicle_type="motorcycle")` for the motorcycle cascade.
- `VehiclesResult.vehicle_ids` for the last cascade level.
- `PlateAPI.walk_vehicles(make, model, ...)`: walks the cascade for one make and model (and its
  trims) and yields each `vehicle_id` once, with `year_from` / `year_to`, `engine_contains`,
  `per_year`, `known_ids` (resume) and `delay` options.
- `RateLimit.topup_remaining` from the `X-Topup-Remaining` header.
- `BadRequestError` (400) and `PermissionDeniedError` (403). `NotFoundError` is now raised for 404.
- `request_id` on every `PlateAPIError`, from the body or the `X-Request-ID` header.
- `max_wait` client option: the longest `Retry-After` the SDK will sleep (default 60 s).
- `py.typed` marker, `User-Agent: plateapi-python/<version>`, `plateapi.__version__`.

### Fixed

- A monthly-quota 429 raises `QuotaExceededError` at once instead of sleeping for an hour and
  retrying.
- A `Retry-After` longer than `max_wait` raises instead of sleeping.
- `health()` no longer removes the API key from the shared session while it runs, and makes a
  single attempt.
- Error messages are the API's own (`detail` / `error`), not a fixed string.
- A lookup that returns `code: "internal_error"` (not billed) is retried before it is returned.

### Changed

- `QuotaExceededError` is now a subclass of `RateLimitError` (still a `PlateAPIError`).
- Documentation URL and `Changelog` link in the package metadata.

## 0.1.0 -- 2026-08-16

- First release: `lookup`, `vehicles`, `usage`, `logs`, `health`, retries with backoff.
