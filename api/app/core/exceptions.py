"""Custom exception classes and FastAPI exception handlers."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class IqbalAIError(Exception):
    """Base exception for all IqbalAI application errors."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(IqbalAIError):
    """JWT missing or invalid."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("AUTHENTICATION_REQUIRED", message, status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedError(IqbalAIError):
    """Caller lacks the required role or scope."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__("PERMISSION_DENIED", message, status.HTTP_403_FORBIDDEN)


class NotFoundError(IqbalAIError):
    """Resource not found (or deliberately hidden from caller)."""

    def __init__(self, message: str = "Not found") -> None:
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


class ConflictError(IqbalAIError):
    """Resource already exists or state conflict."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__("CONFLICT", message, status.HTTP_409_CONFLICT)


def _error_envelope(code: str, message: str) -> dict[str, object]:
    """Build the standard error envelope per ARCH §5.4."""
    return {"error": {"code": code, "message": message}}


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(IqbalAIError)
    async def iqbalai_error_handler(request: Request, exc: IqbalAIError) -> JSONResponse:
        logger.warning(
            "application_error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.code, exc.message),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_envelope("INTERNAL_SERVER_ERROR", "An unexpected error occurred"),
        )
