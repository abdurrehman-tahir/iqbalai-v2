"""Student diagnostic taking API — T-105 (school + independent)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.responses import SuccessEnvelope, success
from app.core.tenant import get_tenant_type
from app.features.diagnostics.schemas import (
    DiagnosticRead,
    DiagnosticResultRead,
    DiagnosticSaveAnswers,
    DiagnosticStartRequest,
)
from app.features.diagnostics.service import DiagnosticService
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.models import UserRole
from app.features.users.repository import UserRepository

router = APIRouter(prefix="/students/me/diagnostics", tags=["diagnostics"])


async def _student_user_id(claims: dict[str, object], db: AsyncSession) -> tuple[str, str]:
    """Return (user_id, tenant_type) for school or independent student."""
    tenant = get_tenant_type(claims)
    role = str(claims.get("role", ""))
    sub = str(claims.get("sub", ""))
    if tenant == "independent" or role == "independent_student":
        if role != "independent_student":
            raise PermissionDeniedError("Requires an independent student account")
        user = await IndependentUserRepository(db).get_by_authentik_id(sub)
        if user is None:
            raise NotFoundError("Student not found")
        return user.id, "independent"
    if role != UserRole.STUDENT.value:
        raise PermissionDeniedError("Requires a school student account")
    user_s = await UserRepository(db).get_by_authentik_id(sub)
    if user_s is None or user_s.role != UserRole.STUDENT:
        raise NotFoundError("Student not found")
    return user_s.id, "school"


@router.post(
    "/start",
    response_model=SuccessEnvelope[DiagnosticRead],
    operation_id="student_start_diagnostic",
    summary="Start or resume a diagnostic (optionally generate questions)",
)
async def start_diagnostic(
    payload: DiagnosticStartRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id, tenant = await _student_user_id(claims, db)
    svc = DiagnosticService(db, tenant)  # type: ignore[arg-type]
    if payload.generate:
        state = await svc.start_with_generated_questions(
            student_user_id=user_id,
            subject_id=payload.subject_id,
            framework_id=payload.framework_id,
            target_language=payload.language,
            grade_label=payload.grade_label,
            subject_name=payload.subject_name,
            framework_name=payload.framework_name,
            context_json=payload.context_json,
            question_count=payload.question_count,
        )
    else:
        seeded: list[object] = [q.model_dump() for q in (payload.questions or [])]
        state = await svc.start(
            student_user_id=user_id,
            subject_id=payload.subject_id,
            framework_id=payload.framework_id,
            questions=seeded,
        )
    return success(state.model_dump(mode="json"))


@router.get(
    "/{diagnostic_id}",
    response_model=SuccessEnvelope[DiagnosticRead],
    operation_id="student_get_diagnostic",
    summary="Get diagnostic attempt (for resume)",
)
async def get_diagnostic(
    diagnostic_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user_id, tenant = await _student_user_id(claims, db)
    svc = DiagnosticService(db, tenant)  # type: ignore[arg-type]
    state = await svc.get(diagnostic_id=diagnostic_id)
    return success(state.model_dump(mode="json"))


@router.put(
    "/{diagnostic_id}/answers",
    response_model=SuccessEnvelope[DiagnosticRead],
    operation_id="student_save_diagnostic_answers",
    summary="Save diagnostic answers (pause / progress)",
)
async def save_answers(
    diagnostic_id: str,
    payload: DiagnosticSaveAnswers,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user_id, tenant = await _student_user_id(claims, db)
    svc = DiagnosticService(db, tenant)  # type: ignore[arg-type]
    state = await svc.save_answers(diagnostic_id=diagnostic_id, answers=payload.answers)
    return success(state.model_dump(mode="json"))


@router.post(
    "/{diagnostic_id}/complete",
    response_model=SuccessEnvelope[DiagnosticResultRead],
    operation_id="student_complete_diagnostic",
    summary="Complete diagnostic and return coaching focus areas (never a grade)",
)
async def complete_diagnostic(
    diagnostic_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user_id, tenant = await _student_user_id(claims, db)
    svc = DiagnosticService(db, tenant)  # type: ignore[arg-type]
    result = await svc.complete(diagnostic_id=diagnostic_id)
    return success(result.model_dump(mode="json"))


@router.post(
    "/{diagnostic_id}/finalize-timeout",
    response_model=SuccessEnvelope[DiagnosticResultRead],
    operation_id="student_finalize_diagnostic_timeout",
    summary="Gracefully finalize an expired diagnostic with coaching focus areas",
)
async def finalize_timeout(
    diagnostic_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _user_id, tenant = await _student_user_id(claims, db)
    svc = DiagnosticService(db, tenant)  # type: ignore[arg-type]
    result = await svc.finalize_timeout(diagnostic_id=diagnostic_id)
    return success(result.model_dump(mode="json"))
