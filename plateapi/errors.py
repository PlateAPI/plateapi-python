class PlateAPIError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(self, message, status_code=None, code=None, response=None, request_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.response = response
        self.request_id = request_id


class BadRequestError(PlateAPIError):
    """HTTP 400: invalid plate, state, cascade value or vehicle ID."""


class AuthenticationError(PlateAPIError):
    """HTTP 401: missing, invalid or deactivated API key, or email not verified."""


class PermissionDeniedError(PlateAPIError):
    """HTTP 403: IP not on the key's allowlist, account banned, or the vehicle
    database needs a Starter plan or above."""


class NotFoundError(PlateAPIError):
    """HTTP 404: no vehicle with that vehicle_id."""


class RateLimitError(PlateAPIError):
    """HTTP 429. retry_after is the server's Retry-After in seconds, if sent."""

    def __init__(self, message, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class QuotaExceededError(RateLimitError):
    """HTTP 429 because the monthly lookup quota is used up."""


class ServerError(PlateAPIError):
    """HTTP 5xx after retries. code is lookup_failed or unavailable when the
    API sent one."""

    def __init__(self, message, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
