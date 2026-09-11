"""Lecture wizard API — steps 1–2 + draft auto-save (T-114)."""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.schemas import (
    DiagramSuggestionAccept,
    DiagramSuggestionsRead,
    LectureAccessSettingsRead,
    LectureAccessSettingsUpdate,
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureGenerateRequest,
    LectureImageUploadRead,
    LectureLinkCreate,
    LectureLinkRead,
    LectureParagraphRead,
    LectureRosterRead,
    LectureTeacherTipsRead,
    LectureVersionRead,
    LectureVersionSaveRequest,
    TeacherOfferingRead,
    TeachingMode,
    VoiceTranscribeRead,
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


@router.get(
    "/lectures/{lecture_id}/access",
    response_model=SuccessEnvelope[LectureAccessSettingsRead],
    operation_id="teacher_get_lecture_access_settings",
    summary="Get a lecture's access-restriction settings (T-123, #21)",
    dependencies=[require_role("teacher")],
)
async def get_lecture_access_settings(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.get_lecture_access_settings(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.put(
    "/lectures/{lecture_id}/access",
    response_model=SuccessEnvelope[LectureAccessSettingsRead],
    operation_id="teacher_set_lecture_access_settings",
    summary="Replace a lecture's access restrictions; empty list clears to default (T-123, #21)",
    dependencies=[require_role("teacher")],
)
async def set_lecture_access_settings(
    lecture_id: str,
    payload: LectureAccessSettingsUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.set_lecture_access_settings(claims, lecture_id, payload)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/roster",
    response_model=SuccessEnvelope[LectureRosterRead],
    operation_id="teacher_get_lecture_roster",
    summary="Grade roster (sections + students) for the access-restriction picker (T-123, #21)",
    dependencies=[require_role("teacher")],
)
async def get_lecture_roster(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.get_lecture_roster(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/teacher-tips",
    response_model=SuccessEnvelope[LectureTeacherTipsRead],
    operation_id="teacher_get_lecture_teacher_tips",
    summary="Delivery tips + technique demo + real-world examples (T-124, #28, #41)",
    dependencies=[require_role("teacher")],
)
async def get_lecture_teacher_tips(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.get_lecture_teacher_tips(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/versions/current",
    response_model=SuccessEnvelope[LectureVersionRead],
    operation_id="teacher_get_current_lecture_version",
    summary="Load the current version's content into the TipTap editor (T-130)",
    dependencies=[require_role("teacher")],
)
async def get_current_lecture_version(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.get_current_lecture_version(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lectures/{lecture_id}/versions",
    response_model=SuccessEnvelope[LectureVersionRead],
    operation_id="teacher_save_lecture_version",
    summary="Save a TipTap edit as a new immutable lecture version (T-130, #29-#31)",
    dependencies=[require_role("teacher")],
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

    svc = LectureWizardService(db)
    result = await svc.save_lecture_version(claims, lecture_id, payload)
    response = success(result.model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.post(
    "/lectures/{lecture_id}/voice-transcribe",
    response_model=SuccessEnvelope[VoiceTranscribeRead],
    operation_id="teacher_transcribe_voice_edit",
    summary="Transcribe a dictated audio clip via faster-whisper (T-131, #29)",
    dependencies=[require_role("teacher")],
)
async def transcribe_voice_edit(
    lecture_id: str,
    audio: UploadFile,
    language: str | None = Query(default=None, pattern="^(en|ur|sd|ps)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audio_bytes = await audio.read()
    svc = LectureWizardService(db)
    result = await svc.transcribe_voice_edit(claims, lecture_id, audio_bytes, language)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lectures/{lecture_id}/images",
    response_model=SuccessEnvelope[LectureImageUploadRead],
    operation_id="teacher_upload_lecture_image",
    summary="Drag-drop image upload into the lecture editor (T-132, #30)",
    dependencies=[require_role("teacher")],
)
async def upload_lecture_image(
    lecture_id: str,
    image: UploadFile,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await image.read()
    svc = LectureWizardService(db)
    result = await svc.upload_lecture_image(claims, lecture_id, data, image.filename or "image")
    return success(result.model_dump(mode="json"))


@router.get(
    "/lectures/{lecture_id}/images/{image_id}",
    response_model=None,
    operation_id="teacher_get_lecture_image",
    summary="Serve a previously-uploaded lecture image (T-132, #30)",
    dependencies=[require_role("teacher")],
)
async def get_lecture_image(
    lecture_id: str,
    image_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = LectureWizardService(db)
    data, filename = await svc.get_lecture_image(claims, lecture_id, image_id)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type)


@router.get(
    "/lectures/{lecture_id}/diagram-suggestions",
    response_model=SuccessEnvelope[DiagramSuggestionsRead],
    operation_id="teacher_get_diagram_suggestions",
    summary="AI-flagged reference-book diagrams relevant to this lecture (T-132, #30)",
    dependencies=[require_role("teacher")],
)
async def get_diagram_suggestions(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.suggest_diagrams(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@router.post(
    "/lectures/{lecture_id}/diagram-suggestions/accept",
    response_model=SuccessEnvelope[LectureImageUploadRead],
    operation_id="teacher_accept_diagram_suggestion",
    summary="Render + insert an accepted reference-book diagram (T-132, #30)",
    dependencies=[require_role("teacher")],
)
async def accept_diagram_suggestion(
    lecture_id: str,
    payload: DiagramSuggestionAccept,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = LectureWizardService(db)
    result = await svc.accept_diagram_suggestion(claims, lecture_id, payload)
    return success(result.model_dump(mode="json"))
