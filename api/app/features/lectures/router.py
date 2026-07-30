"""Lecture wizard API — steps 1–2 + draft auto-save (T-114)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.schemas import (
    LectureDraftRead,
    LectureDraftUpsert,
    TeacherOfferingRead,
    WizardCurriculumRead,
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
