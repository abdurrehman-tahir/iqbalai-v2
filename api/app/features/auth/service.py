"""Auth service — post-login logic (T-016)."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountDeactivatedError, AccountSuspendedError
from app.core.tenant import get_tenant_type
from app.features.independent_users.models import IndependentUserAccountStatus
from app.features.independent_users.service import IndependentUserService
from app.features.tos.repository import TosRepository
from app.features.users.models import UserAccountStatus
from app.features.users.service import UserService

logger = structlog.get_logger(__name__)


class AuthService:
    """Handles post-OIDC-callback business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_svc = UserService(session)
        self._independent_user_svc = IndependentUserService(session)
        self._tos_repo = TosRepository(session)

    async def post_login(self, claims: dict[str, object]) -> dict[str, object]:
        """Called on every OIDC callback. Upserts the User row and checks ToS status.

        Returns a dict describing the login result so the frontend can decide
        whether to show the ToS modal.
        """
        tenant_type = get_tenant_type(claims)
        if tenant_type == "independent":
            return await self._post_login_independent(claims)
        return await self._post_login_school(claims)

    async def _post_login_independent(self, claims: dict[str, object]) -> dict[str, object]:
        authentik_id = str(claims.get("sub", ""))
        existing_any = await self._independent_user_svc.get_by_authentik_id_any(authentik_id)
        if existing_any is not None:
            if existing_any.deleted_at is not None:
                raise AccountDeactivatedError()
            if existing_any.status == IndependentUserAccountStatus.SUSPENDED:
                raise AccountSuspendedError()

        user, is_first_login = await self._independent_user_svc.get_or_create_from_jwt(claims)

        if user.status == IndependentUserAccountStatus.SUSPENDED:
            current_tos = await self._tos_repo.get_current_tos()
            return {
                "user_id": user.id,
                "email": user.email,
                "role": user.role.value,
                "tenant_type": "independent",
                "is_first_login": is_first_login,
                "tos_acceptance_required": current_tos is not None,
                "current_tos_version_id": current_tos.id if current_tos else None,
                "account_status": user.status.value,
            }

        current_tos = await self._tos_repo.get_current_tos()
        tos_accepted = True
        if current_tos is not None:
            tos_accepted = await self._tos_repo.has_accepted_tos(user.id, current_tos.id)

        logger.info(
            "post_login_independent",
            user_id=user.id,
            role=user.role.value,
            is_first_login=is_first_login,
            tos_accepted=tos_accepted,
        )

        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
            "tenant_type": "independent",
            "is_first_login": is_first_login,
            "tos_acceptance_required": not tos_accepted,
            "current_tos_version_id": current_tos.id if current_tos else None,
            "account_status": user.status.value,
        }

    async def _post_login_school(self, claims: dict[str, object]) -> dict[str, object]:
        authentik_id = str(claims.get("sub", ""))
        existing_any = await self._user_svc.get_by_authentik_id_any(authentik_id)
        if existing_any is not None:
            is_deactivated = (
                existing_any.deleted_at is not None
                or existing_any.status == UserAccountStatus.DEACTIVATED
            )
            if is_deactivated:
                raise AccountDeactivatedError()
            if existing_any.status == UserAccountStatus.SUSPENDED:
                raise AccountSuspendedError()

        user, is_first_login = await self._user_svc.get_or_create_from_jwt(claims)

        # Suspended users must re-accept ToS before proceeding (Flow 1 §5.6).
        if user.status == UserAccountStatus.SUSPENDED:
            current_tos = await self._tos_repo.get_current_tos()
            logger.info(
                "post_login_suspended",
                user_id=user.id,
                role=user.role.value,
            )
            return {
                "user_id": user.id,
                "email": user.email,
                "role": user.role.value,
                "tenant_type": "school",
                "is_first_login": is_first_login,
                "tos_acceptance_required": current_tos is not None,
                "current_tos_version_id": current_tos.id if current_tos else None,
                "account_status": user.status.value,
            }

        # Check ToS acceptance status
        current_tos = await self._tos_repo.get_current_tos()
        tos_accepted = True
        if current_tos is not None:
            tos_accepted = await self._tos_repo.has_accepted_tos(user.id, current_tos.id)

        logger.info(
            "post_login",
            user_id=user.id,
            role=user.role.value,
            is_first_login=is_first_login,
            tos_accepted=tos_accepted,
        )

        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
            "tenant_type": "school",
            "district_id": user.district_id,
            "school_id": user.school_id,
            "is_first_login": is_first_login,
            "tos_acceptance_required": not tos_accepted,
            "current_tos_version_id": current_tos.id if current_tos else None,
            "account_status": user.status.value,
        }
