"""Shared FastAPI dependencies — auth, DB session, permission checks."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

import structlog
from fastapi import Depends, Request, params
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.db.session import async_session_factory

logger = structlog.get_logger(__name__)

# Role hierarchy per ARCH §6.7 + §6.19
ROLE_HIERARCHY: dict[str, int] = {
    "platform_admin": 6,
    "district_admin": 5,
    "school_admin": 4,
    "coordinator": 3,
    "teacher": 2,
    "student": 1,
    "parent": 1,
}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for the request lifetime."""
    async with async_session_factory() as session:
        yield session


def get_current_user(request: Request) -> dict[str, object]:
    """Extract validated JWT claims set by AuthMiddleware."""
    claims: dict[str, object] | None = getattr(request.state, "claims", None)
    if claims is None:
        raise AuthenticationError()
    return claims


def require_role(required_role: str) -> params.Depends:
    """Dependency factory: require the caller to have `required_role` or higher.

    Per ARCH §6.19: require_role(X) = X OR HIGHER within the caller's scope.
    Scope enforcement (school_id, district_id) is done per endpoint as needed.

    Example:
        @router.get("/teachers", dependencies=[require_role("coordinator")])
        async def list_teachers(...): ...
    """
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    def _check(claims: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
        caller_role = str(claims.get("role", ""))
        caller_level = ROLE_HIERARCHY.get(caller_role, 0)
        if caller_level < required_level:
            logger.warning(
                "permission_denied",
                caller_role=caller_role,
                required_role=required_role,
                sub=str(claims.get("sub", "")),
            )
            raise PermissionDeniedError(
                f"Requires role '{required_role}' or higher (caller has '{caller_role}')"
            )
        return claims

    return cast(params.Depends, Depends(_check))


def require_scope(required_role: str, scope_field: str) -> params.Depends:
    """Dependency factory: like require_role but also checks scope field matches JWT claim.

    Used for district_admin scoping to their district, school_admin to their school, etc.
    Stub — full scope logic added per-feature as needed.
    """
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    def _check(claims: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
        caller_role = str(claims.get("role", ""))
        caller_level = ROLE_HIERARCHY.get(caller_role, 0)
        # Platform admin bypasses all scope checks
        if caller_level == ROLE_HIERARCHY["platform_admin"]:
            return claims
        if caller_level < required_level:
            raise PermissionDeniedError(
                f"Requires role '{required_role}' or higher (caller has '{caller_role}')"
            )
        # Scope check: the requested resource's scope_field must match the caller's JWT claim
        # Full enforcement happens in the repository layer via RLS + service checks
        return claims

    return cast(params.Depends, Depends(_check))
