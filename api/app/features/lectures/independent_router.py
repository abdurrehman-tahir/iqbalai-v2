"""Independent teacher lecture wizard API — T-125."""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.independent_service import IndependentLectureWizardService
from app.features.lectures.schemas import (
    EditSessionHeartbeatRequest,
    EditSessionRead,
    EditSessionStartRequest,
    IndependentLectureGenerateRequest,
    IndependentLectureRead,
    IndependentWizardReferenceRead,
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureImageUploadRead,
    LectureParagraphRead,
    LectureVersionRead,
    LectureVersionSaveRequest,
    TeachingMode,
    VoiceTranscribeRead,
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


@router.get(
    "/lectures/{lecture_id}/versions/current",
    response_model=SuccessEnvelope[LectureVersionRead],
    operation_id="independent_teacher_get_current_lecture_version",
    summary="Load the current version's content into the TipTap editor (T-130)",
    dependencies=[require_role("independent_teacher")],
)
async def get_current_lecture_version(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    result = await svc.get_current_lecture_version(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lectures/{lecture_id}/versions",
    response_model=SuccessEnvelope[LectureVersionRead],
    operation_id="independent_teacher_save_lecture_version",
    summary="Save a TipTap edit as a new immutable lecture version (T-130, #29-#31)",
    dependencies=[require_role("independent_teacher")],
)
async def save_lecture_version(
    lecture_id: str,
    payload: LectureVersionSaveRequest,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = IndependentLectureWizardService(db)
    result = await svc.save_lecture_version(claims, lecture_id, payload)
    response = success(result.model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.post(
    "/lectures/{lecture_id}/voice-transcribe",
    response_model=SuccessEnvelope[VoiceTranscribeRead],
    operation_id="independent_teacher_transcribe_voice_edit",
    summary="Transcribe a dictated audio clip via faster-whisper (T-131, #29)",
    dependencies=[require_role("independent_teacher")],
)
async def transcribe_voice_edit(
    lecture_id: str,
    audio: UploadFile,
    language: str | None = Query(default=None, pattern="^(en|ur|sd|ps)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audio_bytes = await audio.read()
    svc = IndependentLectureWizardService(db)
    result = await svc.transcribe_voice_edit(claims, lecture_id, audio_bytes, language)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lectures/{lecture_id}/images",
    response_model=SuccessEnvelope[LectureImageUploadRead],
    operation_id="independent_teacher_upload_lecture_image",
    summary="Drag-drop image upload into the lecture editor (T-132, #30)",
    dependencies=[require_role("independent_teacher")],
)
async def upload_lecture_image(
    lecture_id: str,
    image: UploadFile,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await image.read()
    svc = IndependentLectureWizardService(db)
    result = await svc.upload_lecture_image(claims, lecture_id, data, image.filename or "image")
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/images/{image_id}",
    response_model=None,
    operation_id="independent_teacher_get_lecture_image",
    summary="Serve a previously-uploaded lecture image (T-132, #30)",
    dependencies=[require_role("independent_teacher")],
)
async def get_lecture_image(
    lecture_id: str,
    image_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = IndependentLectureWizardService(db)
    data, filename = await svc.get_lecture_image(claims, lecture_id, image_id)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type)


@router.post(
    "/edit-sessions",
    response_model=SuccessEnvelope[EditSessionRead],
    operation_id="independent_teacher_start_edit_session",
    summary="Open an effort-tracking edit session (T-133, #31)",
    status_code=201,
    dependencies=[require_role("independent_teacher")],
)
async def start_edit_session(
    payload: EditSessionStartRequest,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = IndependentLectureWizardService(db)
    result = await svc.start_edit_session(claims, payload)
    response = success(result.model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.post(
    "/edit-sessions/{edit_session_id}/heartbeat",
    response_model=SuccessEnvelope[EditSessionRead],
    operation_id="independent_teacher_heartbeat_edit_session",
    summary="30s effort-tracking heartbeat — cumulative totals (T-133, #31)",
    dependencies=[require_role("independent_teacher")],
)
async def heartbeat_edit_session(
    edit_session_id: str,
    payload: EditSessionHeartbeatRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    result = await svc.heartbeat_edit_session(claims, edit_session_id, payload)
    return success(result.model_dump(mode="json"))


@router.post(
    "/edit-sessions/{edit_session_id}/end",
    response_model=SuccessEnvelope[EditSessionRead],
    operation_id="independent_teacher_end_edit_session",
    summary="Close an effort-tracking edit session (T-133, #31)",
    dependencies=[require_role("independent_teacher")],
)
async def end_edit_session(
    edit_session_id: str,
    payload: EditSessionHeartbeatRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentLectureWizardService(db)
    result = await svc.end_edit_session(claims, edit_session_id, payload)
    return success(result.model_dump(mode="json"))
