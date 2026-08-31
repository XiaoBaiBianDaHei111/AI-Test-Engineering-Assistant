"""Application-level exceptions mapped to a consistent API error shape.

Every error returned by the API uses the same envelope::

    {"code": str, "message": str, "detail": dict}
"""


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    def __init__(
        self,
        status_code: int = 400,
        code: str = "BAD_REQUEST",
        message: str = "Bad request",
        detail: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", detail: dict | None = None) -> None:
        super().__init__(status_code=404, code="NOT_FOUND", message=message, detail=detail)


class ConflictError(AppError):
    """Raised when a write violates a uniqueness or integrity constraint."""

    def __init__(self, message: str = "Resource conflict", detail: dict | None = None) -> None:
        super().__init__(status_code=409, code="CONFLICT", message=message, detail=detail)


class InvalidTransitionError(AppError):
    """Raised when a state-machine transition is not allowed (409, code=INVALID_TRANSITION)."""

    def __init__(self, message: str = "Invalid status transition", detail: dict | None = None) -> None:
        super().__init__(
            status_code=409,
            code="INVALID_TRANSITION",
            message=message,
            detail=detail,
        )


class ValidationFailedError(AppError):
    """Raised for cross-field / business-rule validation that Pydantic cannot express."""

    def __init__(self, message: str = "Validation failed", detail: dict | None = None) -> None:
        super().__init__(
            status_code=422,
            code="VALIDATION_ERROR",
            message=message,
            detail=detail,
        )
