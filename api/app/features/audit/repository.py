"""Audit repository — read-only DB access for the audit log feature (T-025).

Write access is exclusively via app/infrastructure/audit/log.py.
This repository is read-only (SELECT only) in keeping with the immutability contract.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.audit.models import AuditLogEntry

logger = structlog.get_logger(__name__)


class AuditRepository:
    """Read-only access to audit_log rows. Called only from the router layer."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self,
        school_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Return audit entries newest-first, optionally scoped to a school.

        Platform Admin callers pass school_id=None to see platform-wide entries.
        Passing a school_id restricts results to that tenant.
        """
        stmt = select(AuditLogEntry)

        if school_id is not None:
            stmt = stmt.where(AuditLogEntry.school_id == school_id)

        stmt = stmt.order_by(AuditLogEntry.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_actor(
        self,
        actor_id: str,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        """Return the most recent audit entries for a specific actor, newest-first."""
        stmt = (
            select(AuditLogEntry)
            .where(AuditLogEntry.actor_id == actor_id)
            .order_by(AuditLogEntry.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
