"""Student enrollment API endpoints — T-077."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.student_enrollments.schemas import (
    EnrolledStudentRead,
    StudentEnrollmentCreate,
    StudentEnrollmentRead,
)
from app.features.student_enrollments.service import StudentEnrollmentService

router = APIRouter(prefix="/grades/{grade_id}/enrollments", tags=["student-enrollments"])


def _to_read(enrollment: Any, student: Any) -> dict[str, Any]:
    return StudentEnrollmentRead(
        id=enrollment.id,
        school_id=enrollment.school_id,
        student_user_id=enrollment.student_user_id,
        grade_id=enrollment.grade_id,
        section_id=enrollment.section_id,
        academic_session=enrollment.academic_session,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
        student=EnrolledStudentRead.model_validate(student),
    ).model_dump()


@router.post(
    "/",
    response_model=SuccessEnvelope[StudentEnrollmentRead],
    operation_id="student_enrollments_create",
    summary="Enroll a student into a grade and section",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def enroll_student(
    grade_id: str,
    payload: StudentEnrollmentCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentEnrollmentService(db)
    enrollment, student = await svc.enroll_student(
        grade_id,
        payload,
        claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(_to_read(enrollment, student))
