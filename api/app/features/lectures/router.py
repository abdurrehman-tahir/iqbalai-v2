"""Lecture wizard API — steps 1–2 + draft auto-save (T-114)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.schemas import (
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureGenerateRequest,
    LectureLinkCreate,
    LectureLinkRead,
    LectureParagraphRead,
    TeacherOfferingRead,
    TeachingMode,
    WizardCurriculumRead,
    WizardEstimateRead,
    WizardReferenceRead,
    WizardTopicsRead,
)
from app.features.lectures.service import LectureWizardService

router = APIRouter(prefix="/teachers/me", tags=["lecture-wizard"])


@router.get(
    "/offerings",
    response_model=SuccessEnvelope[list[TeacherOfferingRead]],
    operation_id="teacher_list_my_offerings",
    summary="List Grade-Subject offerings assigned to the teacher",
    dependencies=[require_role("teacher")],
)
async def list_my_offerings(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    rows = await svc.list_my_offerings(claims)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/lecture-wizard/curricula",
    response_model=SuccessEnvelope[list[WizardCurriculumRead]],
    operation_id="teacher_list_wizard_curricula",
    summary="List curricula for an assigned Grade-Subject (primary flagged)",
    dependencies=[require_role("teacher")],
)
async def list_wizard_curricula(
    grade_subject_offering_id: str = Query(..., min_length=1, max_length=36),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    rows = await svc.list_curricula_for_offering(claims, grade_subject_offering_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/lecture-wizard/topics",
    response_model=SuccessEnvelope[WizardTopicsRead],
    operation_id="teacher_list_wizard_topics",
    summary="List topic-tree options for a curriculum (freeform when degraded)",
    dependencies=[require_role("teacher")],
)
async def list_wizard_topics(
    curriculum_id: str = Query(..., min_length=1, max_length=36),
    grade_subject_offering_id: str = Query(..., min_length=1, max_length=36),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.list_topics_for_curriculum(claims, curriculum_id, grade_subject_offering_id)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lecture-draft",
    response_model=SuccessEnvelope[LectureDraftRead],
    operation_id="teacher_get_lecture_draft",
    summary="Get the teacher's active lecture wizard draft (resume)",
    dependencies=[require_role("teacher")],
)
async def get_lecture_draft(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    draft = await svc.get_draft(claims)
    return success(draft.model_dump(mode="json"))


@router.put(
    "/lecture-draft",
    response_model=SuccessEnvelope[LectureDraftRead],
    operation_id="teacher_upsert_lecture_draft",
    summary="Auto-save lecture wizard draft state",
    dependencies=[require_role("teacher")],
)
async def upsert_lecture_draft(
    payload: LectureDraftUpsert,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    draft = await svc.upsert_draft(claims, payload)
    return success(draft.model_dump(mode="json"))


@router.get(
    "/lecture-wizard/references",
    response_model=SuccessEnvelope[list[WizardReferenceRead]],
    operation_id="teacher_list_wizard_references",
    summary="List reference books for Step 3 (cross-grade toggle)",
    dependencies=[require_role("teacher")],
)
async def list_wizard_references(
    grade_subject_offering_id: str = Query(..., min_length=1, max_length=36),
    include_cross_grade: bool = Query(False),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    rows = await svc.list_references_for_offering(
        claims,
        grade_subject_offering_id,
        include_cross_grade=include_cross_grade,
    )
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/lecture-wizard/estimate",
    response_model=SuccessEnvelope[WizardEstimateRead],
    operation_id="teacher_get_wizard_estimate",
    summary="Estimated generation time for Step 5",
    dependencies=[require_role("teacher")],
)
async def get_wizard_estimate(
    teaching_mode: TeachingMode = Query(...),
    reference_count: int = Query(0, ge=0, le=20),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = claims  # auth via require_role; estimate is deterministic
    svc = LectureWizardService(db)
    result = svc.estimate(reference_count=reference_count, teaching_mode=teaching_mode)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lecture-wizard/generate",
    response_model=SuccessEnvelope[LectureGenerateRead],
    operation_id="teacher_generate_lecture",
    summary="Commit wizard and transition lecture to GENERATING",
    dependencies=[require_role("teacher")],
)
async def generate_lecture(
    payload: LectureGenerateRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.generate_from_wizard(claims, payload)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/paragraphs",
    response_model=SuccessEnvelope[list[LectureParagraphRead]],
    operation_id="teacher_get_lecture_paragraphs",
    summary="List a lecture's current-version paragraphs with source attribution",
    dependencies=[require_role("teacher")],
)
async def get_lecture_paragraphs(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    rows = await svc.get_lecture_paragraphs(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/lectures/{lecture_id}/links",
    response_model=SuccessEnvelope[list[LectureLinkRead]],
    operation_id="teacher_list_lecture_links",
    summary="List a lecture's cross-grade/subject links (T-122, #21)",
    dependencies=[require_role("teacher")],
)
async def list_lecture_links(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    rows = await svc.list_lecture_links(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.post(
    "/lectures/{lecture_id}/links",
    response_model=SuccessEnvelope[LectureLinkRead],
    operation_id="teacher_create_lecture_link",
    summary="Self-link a lecture into another owned Grade-Subject offering (T-122, #21)",
    dependencies=[require_role("teacher")],
)
async def create_lecture_link(
    lecture_id: str,
    payload: LectureLinkCreate,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = LectureWizardService(db)
    result = await svc.link_lecture(claims, lecture_id, payload)
    response = success(result.model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response
