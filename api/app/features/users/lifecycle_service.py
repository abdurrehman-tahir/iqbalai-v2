"""User lifecycle service — suspend / reactivate / deactivate (T-033)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.notifications.account import notify_account_event

logger = structlog.get_logger(__name__)

_ADMIN_ROLES = frozenset({UserRole.PLATFORM_ADMIN, UserRole.DISTRICT_ADMIN, UserRole.SCHOOL_ADMIN})


def _caller_role(claims: dict[str, object]) -> str:
    return str(claims.get("role", ""))


def _caller_authentik_id(claims: dict[str, object]) -> str:
    return str(claims.get("sub", ""))


def _scope_district_id(claims: dict[str, object]) -> str | None:
    raw = claims.get("district_id")
    return str(raw) if raw else None


def _scope_school_id(claims: dict[str, object]) -> str | None:
    raw = claims.get("school_id")
    return str(raw) if raw else None


class UserLifecycleService:
    """Suspend, reactivate, and deactivate users with scope and admin-floor checks."""

    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._repo = UserRepository(session)
        self._authentik = authentik or get_authentik_client()

    async def list_users(self, claims: dict[str, object], caller_role: str) -> list[User]:
        if ROLE_HIERARCHY.get(caller_role, 0) >= ROLE_HIERARCHY["platform_admin"]:
            return await self._repo.list_scoped()
        if caller_role == "district_admin":
            district_id = _scope_district_id(claims)
            if not district_id:
                raise PermissionDeniedError("District scope required")
            return await self._repo.list_scoped(district_id=district_id)
        if caller_role == "school_admin":
            school_id = _scope_school_id(claims)
            if not school_id:
                raise PermissionDeniedError("School scope required")
            return await self._repo.list_scoped(school_id=school_id)
        raise PermissionDeniedError("Insufficient role to list users")

    def _assert_target_in_scope(
        self, target: User, claims: dict[str, object], caller_role: str
    ) -> None:
        if ROLE_HIERARCHY.get(caller_role, 0) >= ROLE_HIERARCHY["platform_admin"]:
            return
        if caller_role == "district_admin":
            caller_district = _scope_district_id(claims)
            if caller_district != target.district_id:
                raise NotFoundError("User not found")
            return
        if caller_role == "school_admin":
            caller_school = _scope_school_id(claims)
            if caller_school != target.school_id:
                raise NotFoundError("User not found")
            return
        raise PermissionDeniedError("Insufficient role")

    def _assert_can_manage(self, target: User, claims: dict[str, object], caller_role: str) -> None:
        self._assert_target_in_scope(target, claims, caller_role)
        caller_level = ROLE_HIERARCHY.get(caller_role, 0)
        target_level = ROLE_HIERARCHY.get(target.role.value, 0)
        if target_level > caller_level:
            raise PermissionDeniedError("Cannot manage a user with a higher role")

    async def _get_target_or_404(self, user_id: str) -> User:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found")
        return user

    async def _assert_admin_floor(
        self,
        target: User,
        *,
        actor_authentik_id: str,
        action: str,
    ) -> None:
        if target.role not in _ADMIN_ROLES:
            return

        if target.role == UserRole.PLATFORM_ADMIN:
            count = await self._repo.count_active_admins(role=UserRole.PLATFORM_ADMIN)
        elif target.role == UserRole.DISTRICT_ADMIN:
            count = await self._repo.count_active_admins(
                role=UserRole.DISTRICT_ADMIN, district_id=target.district_id
            )
        else:
            count = await self._repo.count_active_admins(
                role=UserRole.SCHOOL_ADMIN, school_id=target.school_id
            )

        if count <= 1:
            if action == "deactivate" and target.authentik_id == actor_authentik_id:
                raise PreconditionFailedError("Last active admin in scope cannot self-deactivate")
            if action in ("deactivate", "suspend"):
                raise PreconditionFailedError("Cannot remove the last active admin in this scope")

    async def suspend_user(
        self,
        user_id: str,
        *,
        claims: dict[str, object],
        actor_id: str,
    ) -> User:
        caller_role = _caller_role(claims)
        target = await self._get_target_or_404(user_id)
        self._assert_can_manage(target, claims, caller_role)

        if target.status == UserAccountStatus.DEACTIVATED:
            raise ValidationError("User is deactivated")
        if target.status == UserAccountStatus.SUSPENDED:
            raise ValidationError("User is already suspended")

        await self._assert_admin_floor(target, actor_authentik_id=actor_id, action="suspend")

        target.status = UserAccountStatus.SUSPENDED
        await self._authentik.deactivate_user(target.authentik_id)
        updated = await self._repo.update(target)

        await audit(
            session=self._session,
            action="user.suspended",
            actor_id=actor_id,
            actor_role=caller_role,
            target_type="user",
            target_id=updated.id,
            district_id=updated.district_id,
            school_id=updated.school_id,
            metadata={"email": updated.email, "role": updated.role.value},
        )
        actor_internal_id = await self._repo.get_by_authentik_id(actor_id)
        await notify_account_event(
            session=self._session,
            template_key="account.suspended",
            recipient_user_id=updated.id,
            school_id=updated.school_id,
            variant="target",
            params={"email": updated.email},
            metadata={"user_id": updated.id},
        )
        if actor_internal_id is not None:
            await notify_account_event(
                session=self._session,
                template_key="account.suspended",
                recipient_user_id=actor_internal_id.id,
                school_id=updated.school_id,
                variant="actor",
                params={"email": updated.email},
                metadata={"user_id": updated.id},
            )
        logger.info("user_suspended", user_id=updated.id, by=actor_id)
        return updated

    async def reactivate_user(
        self,
        user_id: str,
        *,
        claims: dict[str, object],
        actor_id: str,
    ) -> User:
        caller_role = _caller_role(claims)
        target = await self._get_target_or_404(user_id)
        self._assert_can_manage(target, claims, caller_role)

        if target.status == UserAccountStatus.DEACTIVATED or target.deleted_at is not None:
            raise ValidationError("Deactivated users cannot be reactivated")
        if target.status == UserAccountStatus.ACTIVE:
            raise ValidationError("User is already active")

        target.status = UserAccountStatus.ACTIVE
        await self._authentik.activate_user(target.authentik_id)
        updated = await self._repo.update(target)

        await audit(
            session=self._session,
            action="user.reactivated",
            actor_id=actor_id,
            actor_role=caller_role,
            target_type="user",
            target_id=updated.id,
            district_id=updated.district_id,
            school_id=updated.school_id,
            metadata={"email": updated.email, "role": updated.role.value},
        )
        actor_internal = await self._repo.get_by_authentik_id(actor_id)
        await notify_account_event(
            session=self._session,
            template_key="account.reactivated",
            recipient_user_id=updated.id,
            recipient_email=updated.email,
            school_id=updated.school_id,
            variant="target",
            metadata={"user_id": updated.id},
        )
        if actor_internal is not None:
            await notify_account_event(
                session=self._session,
                template_key="account.reactivated",
                recipient_user_id=actor_internal.id,
                school_id=updated.school_id,
                variant="actor",
                params={"email": updated.email},
                metadata={"user_id": updated.id},
            )
        logger.info("user_reactivated", user_id=updated.id, by=actor_id)
        return updated

    async def deactivate_user(
        self,
        user_id: str,
        *,
        claims: dict[str, object],
        actor_id: str,
    ) -> User:
        caller_role = _caller_role(claims)
        target = await self._get_target_or_404(user_id)
        self._assert_can_manage(target, claims, caller_role)

        if target.status == UserAccountStatus.DEACTIVATED:
            raise ValidationError("User is already deactivated")

        await self._assert_admin_floor(target, actor_authentik_id=actor_id, action="deactivate")

        target.status = UserAccountStatus.DEACTIVATED
        target.deleted_at = datetime.now(timezone.utc)
        await self._authentik.deactivate_user(target.authentik_id)
        updated = await self._repo.update(target)

        await audit(
            session=self._session,
            action="user.deactivated",
            actor_id=actor_id,
            actor_role=caller_role,
            target_type="user",
            target_id=updated.id,
            district_id=updated.district_id,
            school_id=updated.school_id,
            metadata={"email": updated.email, "role": updated.role.value},
        )
        await notify_account_event(
            session=self._session,
            template_key="account.deactivated",
            recipient_user_id=updated.id,
            recipient_email=updated.email,
            school_id=updated.school_id,
            metadata={"user_id": updated.id},
        )
        logger.info("user_deactivated", user_id=updated.id, by=actor_id)
        return updated
