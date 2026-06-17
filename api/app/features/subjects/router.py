"""Subject catalogue API endpoints — T-041 (Coordinator and above, §6.19).

Subjects are school-scoped (flow-2 §3.2); every route requires the ``coordinator``
role or higher and acts on the caller's own school catalogue. "Archive" is a custom
action verb (``POST /{id}/archive``) per §5.1 — it flips ``status`` to archived rather
than deleting the row.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.subjects.schemas import SubjectCreate, SubjectRead, SubjectUpdate
from app.features.subjects.service import SubjectService

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[SubjectRead]],
    operation_id="subjects_list",
    summary="List subjects in the caller's school",
    dependencies=[require_role("coordinator")],
)
async def list_subjects(
    include_archived: bool = Query(
        default=False, description="Include archived subjects in the result"
    ),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SubjectService(db)
    subjects = await svc.list_subjects(claims, include_archived=include_archived)
    return success([SubjectRead.model_validate(s).model_dump() for s in subjects])


@router.post(
    "/",
    response_model=SuccessEnvelope[SubjectRead],
    operation_id="subjects_create",
    summary="Create a new subject in the caller's school",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def create_subject(
    payload: SubjectCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SubjectService(db)
    subject = await svc.create_subject(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(SubjectRead.model_validate(subject).model_dump())


@router.get(
    "/{subject_id}",
    response_model=SuccessEnvelope[SubjectRead],
    operation_id="subjects_get",
    summary="Get a single subject",
    dependencies=[require_role("coordinator")],
)
async def get_subject(
    subject_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SubjectService(db)
    subject = await svc.get_subject(subject_id, claims)
    return success(SubjectRead.model_validate(subject).model_dump())


@router.put(
    "/{subject_id}",
    response_model=SuccessEnvelope[SubjectRead],
    operation_id="subjects_update",
    summary="Edit a subject's name or language",
    dependencies=[require_role("coordinator")],
)
async def update_subject(
    subject_id: str,
    payload: SubjectUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SubjectService(db)
    subject = await svc.update_subject(
        subject_id, payload, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(SubjectRead.model_validate(subject).model_dump())


@router.post(
    "/{subject_id}/archive",
    response_model=SuccessEnvelope[SubjectRead],
    operation_id="subjects_archive",
    summary="Archive a subject (status -> archived)",
    dependencies=[require_role("coordinator")],
)
async def archive_subject(
    subject_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SubjectService(db)
    subject = await svc.archive_subject(subject_id, claims, actor_id=str(claims.get("sub", "")))
    return success(SubjectRead.model_validate(subject).model_dump())
