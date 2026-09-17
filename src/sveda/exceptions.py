from typing import Any


class SvedaError(Exception):
    pass


class AuthenticationError(SvedaError):
    pass


class APIError(SvedaError):
    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class TransportError(SvedaError):
    pass


class UnserializableResponse(SvedaError):
    pass
