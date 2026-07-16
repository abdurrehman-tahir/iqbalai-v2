"""ToS service — business logic for ToS/Disclaimer versioning and acceptance."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    TosAcceptanceRequiredError,
    ValidationError,
)
from app.core.tenant import TenantType
from app.features.independent_users.service import IndependentUserService
from app.features.tos.models import DisclaimerVersion, TosVersion, UserTosAcceptance
from app.features.tos.repository import TosRepository
from app.features.users.service import UserService
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)

_MAX_DISCLAIMER_CHARS = 500


class TosService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TosRepository(session)

    def _account_service(self, tenant_type: TenantType) -> UserService | IndependentUserService:
        """Pick the user table the ToS status change applies to.

        Independent users live in their own schema (§3.16) and have no row in
        school.users, so routing a decline/accept to UserService raised NotFound and
        broke independent login at the ToS gate (QA E10/E11). Both services expose the
        same suspend/reactivate pair.
        """
        if tenant_type == "independent":
            return IndependentUserService(self._session)
        return UserService(self._session)

    async def get_current_tos(self) -> TosVersion:
        tos = await self._repo.get_current_tos()
        if tos is None:
            raise NotFoundError("No ToS version published yet")
        return tos

    async def list_tos_versions(self) -> list[TosVersion]:
        return await self._repo.list_tos_versions()

    async def publish_new_tos(
        self,
        content_md: str,
        language: str,
        published_by: str,
    ) -> TosVersion:
        current = await self._repo.get_current_tos()
        next_version = (current.version_number + 1) if current else 1
        tos = TosVersion(
            version_number=next_version,
            content_md=content_md,
            language=language,
            effective_at=datetime.now(timezone.utc),
            published_by=published_by,
        )
        created = await self._repo.create_tos_version(tos)
        await audit(
            session=self._session,
            action="tos.published",
            actor_id=published_by,
            target_type="tos_version",
            target_id=created.id,
            metadata={"version_number": next_version},
        )
        logger.info("tos_version_published", version=next_version, by=published_by)
        return created

    async def accept_tos(
        self,
        user_id: str,
        tos_version_id: str,
        ip_address: str | None = None,
        tenant_type: TenantType = "school",
    ) -> UserTosAcceptance:
        tos = await self._repo.get_tos_by_id(tos_version_id)
        if tos is None:
            raise NotFoundError(f"ToS version {tos_version_id} not found")
        already = await self._repo.has_accepted_tos(user_id, tos_version_id)
        if already:
            raise ConflictError("ToS version already accepted")
        acceptance = await self._repo.record_acceptance(user_id, tos_version_id, ip_address)
        await self._account_service(tenant_type).reactivate_on_tos_accept(user_id)
        await audit(
            session=self._session,
            action="tos.accepted",
            actor_id=user_id,
            target_type="tos_version",
            target_id=tos_version_id,
            ip_address=ip_address,
        )
        return acceptance

    async def decline_tos(
        self,
        user_id: str,
        ip_address: str | None = None,
        tenant_type: TenantType = "school",
    ) -> None:
        """Decline current ToS — suspends the account (Flow 1 §5.6)."""
        current = await self._repo.get_current_tos()
        if current is None:
            raise NotFoundError("No ToS version published yet")
        await self._account_service(tenant_type).suspend_for_tos_decline(user_id)
        await audit(
            session=self._session,
            action="tos.declined",
            actor_id=user_id,
            target_type="tos_version",
            target_id=current.id,
            ip_address=ip_address,
        )
        logger.info("tos_declined", user_id=user_id, tos_version_id=current.id)

    async def check_user_has_accepted_current(self, user_id: str) -> bool:
        """Return True if user has accepted the current (latest) ToS version."""
        current = await self._repo.get_current_tos()
        if current is None:
            return True  # no ToS published yet — allow through
        return await self._repo.has_accepted_tos(user_id, current.id)

    async def require_tos_accepted(self, user_id: str) -> None:
        """Raise TosAcceptanceRequiredError if user has not accepted current ToS."""
        if not await self.check_user_has_accepted_current(user_id):
            raise TosAcceptanceRequiredError()

    # ── Disclaimer ────────────────────────────────────────────────────────────

    async def get_current_disclaimer(self) -> DisclaimerVersion:
        d = await self._repo.get_current_disclaimer()
        if d is None:
            raise NotFoundError("No Disclaimer version published yet")
        return d

    async def list_disclaimer_versions(self) -> list[DisclaimerVersion]:
        return await self._repo.list_disclaimer_versions()

    async def publish_new_disclaimer(
        self,
        content: str,
        language: str,
        published_by: str,
    ) -> DisclaimerVersion:
        if len(content) > _MAX_DISCLAIMER_CHARS:
            raise ValidationError(
                f"Disclaimer must be ≤ {_MAX_DISCLAIMER_CHARS} characters (got {len(content)})"
            )
        current = await self._repo.get_current_disclaimer()
        next_version = (current.version_number + 1) if current else 1
        disclaimer = DisclaimerVersion(
            version_number=next_version,
            content=content,
            language=language,
            effective_at=datetime.now(timezone.utc),
            published_by=published_by,
        )
        created = await self._repo.create_disclaimer_version(disclaimer)
        await audit(
            session=self._session,
            action="disclaimer.published",
            actor_id=published_by,
            target_type="disclaimer_version",
            target_id=created.id,
            metadata={"version_number": next_version},
        )
        logger.info("disclaimer_version_published", version=next_version, by=published_by)
        return created
