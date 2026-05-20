"""Shared FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.db.session import async_session_factory

logger = structlog.get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for the request lifetime."""
    async with async_session_factory() as session:
        yield session


def get_current_user(request: Request) -> dict[str, object]:
    """Extract validated JWT claims from the request state.

    The AuthMiddleware already validated the token; this dependency just
    surfaces the claims for route handlers.
    """
    claims: dict[str, object] | None = getattr(request.state, "claims", None)
    if claims is None:
        raise AuthenticationError()
    return claims


def require_role(required_role: str) -> object:
    """Dependency factory — require the caller to have `required_role` or higher.

    Full implementation in T-008. This stub grants access to platform_admin only.
    """
    ROLE_HIERARCHY: dict[str, int] = {
        "platform_admin": 6,
        "district_admin": 5,
        "school_admin": 4,
        "coordinator": 3,
        "teacher": 2,
        "student": 1,
        "parent": 1,
    }
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    def _check(
        claims: dict[str, object] = Depends(get_current_user),
    ) -> dict[str, object]:
        caller_role = str(claims.get("role", ""))
        caller_level = ROLE_HIERARCHY.get(caller_role, 0)
        if caller_level < required_level:
            raise PermissionDeniedError(
                f"Role '{caller_role}' cannot access this endpoint"
                f" (requires '{required_role}' or higher)"
            )
        return claims

    return Depends(_check)
