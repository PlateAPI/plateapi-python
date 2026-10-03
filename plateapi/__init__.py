from ._version import __version__
from .client import PlateAPI
from .errors import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    PlateAPIError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from .types import (
    HealthStatus,
    LogEntry,
    LogsResult,
    LookupResult,
    RateLimit,
    Usage,
    Vehicle,
    VehicleRecord,
    VehiclesResult,
    WalkedVehicle,
)

__all__ = [
    "PlateAPI",
    "PlateAPIError",
    "AuthenticationError",
    "BadRequestError",
    "PermissionDeniedError",
    "RateLimitError",
    "QuotaExceededError",
    "NotFoundError",
    "ServerError",
    "Vehicle",
    "VehicleRecord",
    "WalkedVehicle",
    "LookupResult",
    "VehiclesResult",
    "RateLimit",
    "Usage",
    "HealthStatus",
    "LogEntry",
    "LogsResult",
    "__version__",
]
