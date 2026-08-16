class PlateAPIError(Exception):
    def __init__(self, message, status_code=None, code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.response = response


class AuthenticationError(PlateAPIError):
    pass


class RateLimitError(PlateAPIError):
    def __init__(self, message, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class QuotaExceededError(PlateAPIError):
    pass


class NotFoundError(PlateAPIError):
    pass


class ServerError(PlateAPIError):
    def __init__(self, message, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
