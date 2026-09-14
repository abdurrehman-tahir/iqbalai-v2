"""Admin comparative teacher metrics API — school tenant (T-139, Flow 5
§3.11 #38). ``require_role("school_admin")`` is the floor; School/District/
Platform Admin each see a wider scope, enforced in the service layer."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.admin_metrics import service
from app.features.admin_metrics.schemas import TeacherMetricsRead
from app.features.admin_metrics.service import MetricsFilters

router = APIRouter(prefix="/admin/teacher-metrics", tags=["admin-metrics"])

_CSV_COLUMNS = [
    "teacher_name",
    "school_name",
    "subject_name",
    "grade_range",
    "lecture_count",
    "avg_originality",
    "avg_depth",
    "avg_cultural_relevance",
    "avg_engagement",
    "avg_alignment",
    "avg_voice_quality",
    "avg_ai_learning",
    "avg_total",
    "avg_topic_relevance_pct",
]


def _filters(
    subject_id: str | None = Query(default=None),
    grade_range: str | None = Query(default=None),
    school_id: str | None = Query(default=None),
) -> MetricsFilters:
    return MetricsFilters(subject_id=subject_id, grade_range=grade_range, school_id=school_id)


@router.get(
    "",
    response_model=SuccessEnvelope[list[TeacherMetricsRead]],
    operation_id="admin_list_teacher_metrics",
    summary="Comparative 7-dim quality metrics across teachers, scoped by admin level (T-139, #38)",
    dependencies=[require_role("school_admin")],
)
async def list_teacher_metrics(
    filters: MetricsFilters = Depends(_filters),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    caller_role = str(claims.get("role", ""))
    rows = await service.get_teacher_metrics(
        db, claims=claims, caller_role=caller_role, filters=filters
    )
    return success([row.model_dump(mode="json") for row in rows])


@router.get(
    "/export",
    operation_id="admin_export_teacher_metrics_csv",
    summary="CSV export of the comparative teacher metrics table (T-139, #38)",
    dependencies=[require_role("school_admin")],
)
async def export_teacher_metrics_csv(
    filters: MetricsFilters = Depends(_filters),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    caller_role = str(claims.get("role", ""))
    rows = await service.get_teacher_metrics(
        db, claims=claims, caller_role=caller_role, filters=filters
    )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.model_dump(mode="json", include=set(_CSV_COLUMNS)))
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="teacher-metrics.csv"'},
    )
