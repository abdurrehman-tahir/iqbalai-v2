"""Audit log write helper — called from every write endpoint (T-025).

Per ARCH §14.10: every mutation is audit-logged. The audit_log table is
immutable (no UPDATE/DELETE). 7-year retention enforced via Celery beat (Phase 2).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def audit(
    *,
    session: AsyncSession,
    action: str,
    actor_id: str | None = None,
    actor_role: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    school_id: str | None = None,
    district_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write an immutable audit log row.

    Call this from every service method that mutates state.
    Example:
        await audit(session=db, action="tos.published", actor_id=user_id,
                    target_type="tos_version", target_id=tos.id)
    """
    # Deferred import avoids circular dependency between infrastructure and features layers
    from app.features.audit.models import AuditLogEntry

    entry = AuditLogEntry(
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        target_type=target_type,
        target_id=target_id,
        school_id=school_id,
        district_id=district_id,
        ip_address=ip_address,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    session.add(entry)
    await session.commit()

    logger.info(
        "audit_logged",
        action=action,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
    )
