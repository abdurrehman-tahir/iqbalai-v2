"""ToS repository — all DB queries for ToS/Disclaimer/Acceptance."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tos.models import DisclaimerVersion, TosVersion, UserTosAcceptance

logger = structlog.get_logger(__name__)


class TosRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current_tos(self) -> TosVersion | None:
        """Return the highest version_number ToS."""
        result = await self._session.execute(
            select(TosVersion).order_by(TosVersion.version_number.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_tos_by_id(self, tos_id: str) -> TosVersion | None:
        result = await self._session.execute(select(TosVersion).where(TosVersion.id == tos_id))
        return result.scalar_one_or_none()

    async def create_tos_version(self, tos: TosVersion) -> TosVersion:
        self._session.add(tos)
        await self._session.commit()
        await self._session.refresh(tos)
        return tos

    async def list_tos_versions(self) -> list[TosVersion]:
        result = await self._session.execute(
            select(TosVersion).order_by(TosVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_acceptance(self, user_id: str, tos_version_id: str) -> UserTosAcceptance | None:
        result = await self._session.execute(
            select(UserTosAcceptance).where(
                UserTosAcceptance.user_id == user_id,
                UserTosAcceptance.tos_version_id == tos_version_id,
            )
        )
        return result.scalar_one_or_none()

    async def has_accepted_tos(self, user_id: str, tos_version_id: str) -> bool:
        return await self.get_acceptance(user_id, tos_version_id) is not None

    async def record_acceptance(
        self,
        user_id: str,
        tos_version_id: str,
        ip_address: str | None = None,
    ) -> UserTosAcceptance:
        acceptance = UserTosAcceptance(
            user_id=user_id,
            tos_version_id=tos_version_id,
            accepted_at=datetime.now(timezone.utc),
            ip_address=ip_address,
        )
        self._session.add(acceptance)
        # Flush, don't commit: the acceptance must not survive on its own if a later step
        # of accept_tos fails. Committing here dead-ended independent users — the row was
        # written, the reactivate step then raised, the caller got "failed to record your
        # acceptance", and every retry hit 409 already-accepted (QA E10/E11). The
        # reactivate/audit steps that follow commit the whole transaction.
        await self._session.flush()
        await self._session.refresh(acceptance)
        return acceptance

    # ── Disclaimer ────────────────────────────────────────────────────────────

    async def get_current_disclaimer(self) -> DisclaimerVersion | None:
        result = await self._session.execute(
            select(DisclaimerVersion).order_by(DisclaimerVersion.version_number.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_disclaimer_version(self, disclaimer: DisclaimerVersion) -> DisclaimerVersion:
        self._session.add(disclaimer)
        await self._session.commit()
        await self._session.refresh(disclaimer)
        return disclaimer

    async def list_disclaimer_versions(self) -> list[DisclaimerVersion]:
        result = await self._session.execute(
            select(DisclaimerVersion).order_by(DisclaimerVersion.version_number.desc())
        )
        return list(result.scalars().all())
