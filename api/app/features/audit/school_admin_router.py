"""School Admin audit log router — scoped read-only (T-039).

School Admins see the last 50 audit entries for their own school only.
school_id is taken from JWT claims — never from query parameters.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import PermissionDeniedError
from app.core.responses import paginated
from app.features.audit.repository import AuditRepository
from app.features.audit.schemas import AuditLogEntryRead

logger = structlog.get_logger(__name__)

SCHOOL_AUDIT_LIMIT = 50

router = APIRouter(
    prefix="/school/admin/audit-log",
    tags=["audit"],
    dependencies=[require_role("school_admin")],
)


@router.get(
    "/",
    summary="List recent audit log entries for the caller's school",
    description=(
        "Returns the 50 most recent immutable audit entries for the School Admin's "
        "school. Cross-school access is not permitted."
    ),
)
async def list_school_audit_log(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    school_id = str(claims.get("school_id", "") or "")
    if not school_id:
        raise PermissionDeniedError("School scope required")

    repo = AuditRepository(db)
    entries = await repo.list_recent(
        school_id=school_id,
        limit=SCHOOL_AUDIT_LIMIT,
        offset=0,
    )

    logger.info(
        "school_audit_log_listed",
        school_id=school_id,
        count=len(entries),
    )

    items = [AuditLogEntryRead.model_validate(e).model_dump() for e in entries]
    return paginated(items=items, total=len(items), page=1, page_size=SCHOOL_AUDIT_LIMIT)
