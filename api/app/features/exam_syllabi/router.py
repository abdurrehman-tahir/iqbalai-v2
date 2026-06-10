"""Exam Syllabi API endpoints — T-020 (Platform Admin only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import DeletedResponse, SuccessEnvelope, success
from app.features.exam_syllabi.schemas import (
    ExamSyllabusCreate,
    ExamSyllabusRead,
    ExamSyllabusUpdate,
    SyllabusTopicCreate,
    SyllabusTopicRead,
)
from app.features.exam_syllabi.service import ExamSyllabiService

router = APIRouter(prefix="/admin/exam-syllabi", tags=["exam-syllabi"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[ExamSyllabusRead]],
    operation_id="list_syllabi",
    summary="List all exam syllabi",
    dependencies=[require_role("platform_admin")],
)
async def list_syllabi(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    syllabi = await svc.list_syllabi()
    return success([ExamSyllabusRead.model_validate(s).model_dump() for s in syllabi])


@router.post(
    "/",
    response_model=SuccessEnvelope[ExamSyllabusRead],
    operation_id="create_syllabus",
    summary="Create a new exam syllabus",
    status_code=201,
    dependencies=[require_role("platform_admin")],
)
async def create_syllabus(
    payload: ExamSyllabusCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    syllabus = await svc.create_syllabus(payload, created_by=str(claims.get("sub", "")))
    return success(ExamSyllabusRead.model_validate(syllabus).model_dump())


@router.get(
    "/{syllabus_id}",
    response_model=SuccessEnvelope[ExamSyllabusRead],
    operation_id="get_syllabus",
    summary="Get a single exam syllabus",
    dependencies=[require_role("platform_admin")],
)
async def get_syllabus(
    syllabus_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    syllabus = await svc.get_syllabus(syllabus_id)
    return success(ExamSyllabusRead.model_validate(syllabus).model_dump())


@router.put(
    "/{syllabus_id}",
    response_model=SuccessEnvelope[ExamSyllabusRead],
    operation_id="update_syllabus",
    summary="Update an exam syllabus (bumps version_number)",
    dependencies=[require_role("platform_admin")],
)
async def update_syllabus(
    syllabus_id: str,
    payload: ExamSyllabusUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    syllabus = await svc.update_syllabus(
        syllabus_id, payload, updated_by=str(claims.get("sub", ""))
    )
    return success(ExamSyllabusRead.model_validate(syllabus).model_dump())


@router.delete(
    "/{syllabus_id}",
    response_model=SuccessEnvelope[DeletedResponse],
    operation_id="delete_syllabus",
    summary="Soft-delete an exam syllabus",
    dependencies=[require_role("platform_admin")],
)
async def delete_syllabus(
    syllabus_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    await svc.delete_syllabus(syllabus_id)
    return success({"deleted": True})


@router.get(
    "/{syllabus_id}/topics",
    response_model=SuccessEnvelope[list[SyllabusTopicRead]],
    operation_id="list_topics",
    summary="List topics for a syllabus",
    dependencies=[require_role("platform_admin")],
)
async def list_topics(
    syllabus_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    topics = await svc.list_topics(syllabus_id)
    return success([SyllabusTopicRead.model_validate(t).model_dump() for t in topics])


@router.post(
    "/{syllabus_id}/topics",
    response_model=SuccessEnvelope[SyllabusTopicRead],
    operation_id="create_topic",
    summary="Create a topic under a syllabus",
    status_code=201,
    dependencies=[require_role("platform_admin")],
)
async def create_topic(
    syllabus_id: str,
    payload: SyllabusTopicCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    topic = await svc.create_topic(syllabus_id, payload)
    return success(SyllabusTopicRead.model_validate(topic).model_dump())


@router.delete(
    "/{syllabus_id}/topics/{topic_id}",
    response_model=SuccessEnvelope[DeletedResponse],
    operation_id="delete_topic",
    summary="Soft-delete a topic",
    dependencies=[require_role("platform_admin")],
)
async def delete_topic(
    syllabus_id: str,
    topic_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamSyllabiService(db)
    await svc.delete_topic(topic_id)
    return success({"deleted": True})
