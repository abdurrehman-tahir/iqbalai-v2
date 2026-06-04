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
from app.features.tos.models import DisclaimerVersion, TosVersion
from app.features.tos.repository import TosRepository

logger = structlog.get_logger(__name__)

_MAX_DISCLAIMER_CHARS = 500


class TosService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TosRepository(session)

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
        logger.info("tos_version_published", version=next_version, by=published_by)
        return created

    async def accept_tos(
        self,
        user_id: str,
        tos_version_id: str,
        ip_address: str | None = None,
    ) -> object:
        tos = await self._repo.get_tos_by_id(tos_version_id)
        if tos is None:
            raise NotFoundError(f"ToS version {tos_version_id} not found")
        already = await self._repo.has_accepted_tos(user_id, tos_version_id)
        if already:
            raise ConflictError("ToS version already accepted")
        return await self._repo.record_acceptance(user_id, tos_version_id, ip_address)

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
        logger.info("disclaimer_version_published", version=next_version, by=published_by)
        return created
