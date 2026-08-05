"""Independent teacher lecture wizard API — T-125."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.independent_service import IndependentLectureWizardService
from app.features.lectures.schemas import (
    IndependentLectureGenerateRequest,
    IndependentLectureRead,
    IndependentWizardReferenceRead,
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureParagraphRead,
    TeachingMode,
    WizardEstimateRead,
)

router = APIRouter(prefix="/independent/teachers/me", tags=["independent-lecture-wizard"])


@router.get(
    "/lecture-wizard/references",
    response_model=SuccessEnvelope[list[IndependentWizardReferenceRead]],
    operation_id="independent_teacher_list_wizard_references",
    summary="List the teacher's own private references for Step 3 (T-125)",
    dependencies=[require_role("independent_teacher")],
)
async def list_wizard_references(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    rows = await svc.list_my_references(claims)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/lecture-draft",
    response_model=SuccessEnvelope[LectureDraftRead],
    operation_id="independent_teacher_get_lecture_draft",
    summary="Get the teacher's active lecture wizard draft (resume)",
    dependencies=[require_role("independent_teacher")],
)
async def get_lecture_draft(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    draft = await svc.get_draft(claims)
    return success(draft.model_dump(mode="json"))


@router.put(
    "/lecture-draft",
    response_model=SuccessEnvelope[LectureDraftRead],
    operation_id="independent_teacher_upsert_lecture_draft",
    summary="Auto-save lecture wizard draft state",
    dependencies=[require_role("independent_teacher")],
)
async def upsert_lecture_draft(
    payload: LectureDraftUpsert,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    draft = await svc.upsert_draft(claims, payload)
    return success(draft.model_dump(mode="json"))


@router.get(
    "/lecture-wizard/estimate",
    response_model=SuccessEnvelope[WizardEstimateRead],
    operation_id="independent_teacher_get_wizard_estimate",
    summary="Estimated generation time",
    dependencies=[require_role("independent_teacher")],
)
async def get_wizard_estimate(
    teaching_mode: TeachingMode = Query(...),
    reference_count: int = Query(0, ge=0, le=20),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = claims  # auth via require_role; estimate is deterministic
    svc = IndependentLectureWizardService(db)
    result = svc.estimate(reference_count=reference_count, teaching_mode=teaching_mode)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lecture-wizard/generate",
    response_model=SuccessEnvelope[LectureGenerateRead],
    operation_id="independent_teacher_generate_lecture",
    summary="Commit wizard and transition lecture to GENERATING (T-125)",
    dependencies=[require_role("independent_teacher")],
)
async def generate_lecture(
    payload: IndependentLectureGenerateRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    result = await svc.generate_from_wizard(claims, payload)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}",
    response_model=SuccessEnvelope[IndependentLectureRead],
    operation_id="independent_teacher_get_lecture",
    summary="Lecture status, for the frontend to poll until generation completes (T-125)",
    dependencies=[require_role("independent_teacher")],
)
async def get_lecture(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    result = await svc.get_lecture(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/paragraphs",
    response_model=SuccessEnvelope[list[LectureParagraphRead]],
    operation_id="independent_teacher_get_lecture_paragraphs",
    summary="List a lecture's current-version paragraphs with source attribution",
    dependencies=[require_role("independent_teacher")],
)
async def get_lecture_paragraphs(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    rows = await svc.get_lecture_paragraphs(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])
