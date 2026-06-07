"""Audit log admin router — Platform Admin only (T-025).

Per ARCH §14.10: audit_log is immutable. This router exposes read-only
endpoints. There are no POST/PUT/DELETE endpoints by design.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.responses import PaginatedEnvelope, paginated
from app.features.audit.repository import AuditRepository
from app.features.audit.schemas import AuditLogEntryRead

logger = structlog.get_logger(__name__)

# Platform Admin access only — audit log contains PII-adjacent data from all tenants
router = APIRouter(
    prefix="/admin/audit-log",
    tags=["audit"],
    dependencies=[require_role("platform_admin")],
)


@router.get(
    "/",
    response_model=PaginatedEnvelope[AuditLogEntryRead],
    operation_id="list_audit_log",
    summary="List recent audit log entries (Platform Admin only)",
    description=(
        "Returns audit entries newest-first. Filter by school_id to scope results "
        "to a specific school. Leave school_id unset to see platform-wide entries."
    ),
)
async def list_audit_log(
    school_id: str | None = Query(default=None, description="Filter by school tenant"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Fetch a page of audit log entries, optionally scoped to a school."""
    repo = AuditRepository(db)
    entries = await repo.list_recent(school_id=school_id, limit=limit, offset=offset)

    logger.info(
        "audit_log_listed",
        school_id=school_id,
        count=len(entries),
        offset=offset,
    )

    items = [AuditLogEntryRead.model_validate(e).model_dump() for e in entries]

    # page is 1-indexed for the frontend; derive from limit/offset
    page = (offset // limit) + 1 if limit > 0 else 1

    return paginated(items=items, total=len(entries), page=page, page_size=limit)
