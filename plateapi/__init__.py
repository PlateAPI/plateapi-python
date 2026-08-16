from .client import PlateAPI
from .errors import (
    PlateAPIError,
    AuthenticationError,
    RateLimitError,
    QuotaExceededError,
    NotFoundError,
    ServerError,
)
from .types import Vehicle, LookupResult, VehiclesResult, RateLimit, Usage, HealthStatus, LogEntry, LogsResult

__version__ = "0.1.0"
__all__ = [
    "PlateAPI",
    "PlateAPIError",
    "AuthenticationError",
    "RateLimitError",
    "QuotaExceededError",
    "NotFoundError",
    "ServerError",
    "Vehicle",
    "LookupResult",
    "VehiclesResult",
    "RateLimit",
    "Usage",
    "HealthStatus",
    "LogEntry",
    "LogsResult",
]
