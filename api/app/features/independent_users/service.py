"""Independent user service — JWT upsert and profile helpers."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.independent_users.repository import IndependentUserRepository

logger = structlog.get_logger(__name__)


def parse_independent_user_role(role_claim: object) -> IndependentUserRole:
    raw = str(role_claim or IndependentUserRole.INDEPENDENT_STUDENT.value).strip()
    try:
        return IndependentUserRole(raw)
    except ValueError:
        pass
    try:
        return IndependentUserRole[raw.upper()]
    except KeyError:
        return IndependentUserRole.INDEPENDENT_STUDENT


class IndependentUserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = IndependentUserRepository(session)

    async def get_by_authentik_id_any(self, authentik_id: str) -> IndependentUser | None:
        return await self._repo.get_by_authentik_id_any(authentik_id)

    async def get_me(self, authentik_id: str) -> IndependentUser | None:
        """Return the IndependentUser for the currently authenticated user.

        The independent-tenant twin of ``UserService.get_me`` — ToS acceptance resolves
        the caller through whichever of the two applies (QA E10/E11).
        """
        return await self._repo.get_by_authentik_id(authentik_id)

    async def suspend_for_tos_decline(self, user_id: str) -> IndependentUser:
        """Mark the account SUSPENDED when the user declines ToS (Flow 1 §5.6)."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        user.status = IndependentUserAccountStatus.SUSPENDED
        return await self._repo.update(user)

    async def reactivate_on_tos_accept(self, user_id: str) -> IndependentUser:
        """Restore ACTIVE when a suspended user accepts the current ToS."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.status == IndependentUserAccountStatus.SUSPENDED:
            user.status = IndependentUserAccountStatus.ACTIVE
            return await self._repo.update(user)
        return user

    async def get_or_create_from_jwt(
        self, claims: dict[str, object]
    ) -> tuple[IndependentUser, bool]:
        authentik_id = str(claims.get("sub", ""))
        email = str(claims.get("email", "")).strip().lower()

        existing = await self._repo.get_by_authentik_id(authentik_id)
        if existing:
            return existing, False

        if email:
            by_email = await self._repo.get_by_email(email)
            if by_email is not None:
                if by_email.authentik_id != authentik_id:
                    by_email.authentik_id = authentik_id
                    by_email = await self._repo.update(by_email)
                return by_email, False

        user = IndependentUser(
            authentik_id=authentik_id,
            email=email,
            display_name=str(claims.get("name", claims.get("email", ""))),
            role=parse_independent_user_role(claims.get("role")),
            status=IndependentUserAccountStatus.ACTIVE,
            language_preference=str(claims.get("language_preference", "en"))[:10],
        )
        created = await self._repo.create(user)
        logger.info("independent_user_created", user_id=created.id, role=created.role.value)
        return created, True
