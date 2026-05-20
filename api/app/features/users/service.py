"""User service — business logic."""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.features.users.schemas import UserCreate

logger = structlog.get_logger(__name__)


class UserService:
    """Business logic for user management."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_or_create_from_jwt(self, claims: dict[str, object]) -> User:
        """Upsert a user record from JWT claims on first OIDC login."""
        authentik_id = str(claims.get("sub", ""))
        existing = await self._repo.get_by_authentik_id(authentik_id)
        if existing:
            return existing

        user = User(
            authentik_id=authentik_id,
            email=str(claims.get("email", "")),
            display_name=str(claims.get("name", claims.get("email", ""))),
            role=UserRole(str(claims.get("role", "student"))),
            school_id=str(claims.get("school_id", "")) or None,
            district_id=str(claims.get("district_id", "")) or None,
        )
        created = await self._repo.create(user)
        logger.info("user_created", user_id=created.id, role=created.role.value)
        return created
