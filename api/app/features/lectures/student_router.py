"""Student lecture study session + text viewer API (T-151 / T-152)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.lecture_session import LectureSessionService
from app.features.lectures.schemas import (
    LectureAudioCacheRead,
    LectureAudioRequest,
    LectureSessionModeUpdateRequest,
    LectureSessionOpenRequest,
    LectureSessionRead,
    StudentLectureCardRead,
    StudentLectureViewerRead,
)
from app.features.lectures.student_viewer import StudentLectureViewerService

student_session_router = APIRouter(
    prefix="/students/me/lectures",
    tags=["student-lecture-sessions"],
)


# --- Static /sessions/* paths first (before /{lecture_id}) ---------------


@student_session_router.get(
    "/sessions/{session_id}",
    response_model=SuccessEnvelope[LectureSessionRead],
    operation_id="student_get_lecture_session",
    summary="Get a lecture study session (lazy inactivity end) (T-151)",
    dependencies=[require_role("student")],
)
async def get_lecture_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureSessionService(db).get_session(claims, session_id)
    return success(result.model_dump(mode="json"))


@student_session_router.post(
    "/sessions/{session_id}/activity",
    response_model=SuccessEnvelope[LectureSessionRead],
    operation_id="student_touch_lecture_session",
    summary="Bump last_activity_at for an active lecture session (T-151)",
    dependencies=[require_role("student")],
)
async def touch_lecture_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureSessionService(db).touch_activity(claims, session_id)
    return success(result.model_dump(mode="json"))


@student_session_router.patch(
    "/sessions/{session_id}/mode",
    response_model=SuccessEnvelope[LectureSessionRead],
    operation_id="student_set_lecture_session_mode",
    summary="Switch lecture session mode text|voice (T-151/T-154)",
    dependencies=[require_role("student")],
)
async def set_lecture_session_mode(
    session_id: str,
    payload: LectureSessionModeUpdateRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureSessionService(db).set_mode(claims, session_id, payload)
    return success(result.model_dump(mode="json"))


@student_session_router.post(
    "/sessions/{session_id}/end",
    response_model=SuccessEnvelope[LectureSessionRead],
    operation_id="student_end_lecture_session",
    summary="End a lecture study session (T-151)",
    dependencies=[require_role("student")],
)
async def end_lecture_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureSessionService(db).end_session(claims, session_id)
    return success(result.model_dump(mode="json"))


# --- Lecture list / open viewer / open session ---------------------------


@student_session_router.get(
    "",
    response_model=SuccessEnvelope[list[StudentLectureCardRead]],
    operation_id="student_list_my_lectures",
    summary="List published lectures the student can open (T-152)",
    dependencies=[require_role("student")],
)
async def list_my_lectures(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await StudentLectureViewerService(db).list_my_lectures(claims)
    return success([r.model_dump(mode="json") for r in rows])


@student_session_router.post(
    "/{lecture_id}/open",
    response_model=SuccessEnvelope[StudentLectureViewerRead],
    operation_id="student_open_lecture_viewer",
    summary="Open published lecture viewer (starts T-151 session) (T-152)",
    dependencies=[require_role("student")],
)
async def open_lecture_viewer(
    lecture_id: str,
    payload: LectureSessionOpenRequest | None = None,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await StudentLectureViewerService(db).open_viewer(
        claims, lecture_id, mode_payload=payload
    )
    return success(result.model_dump(mode="json"))


@student_session_router.post(
    "/{lecture_id}/sessions",
    response_model=SuccessEnvelope[LectureSessionRead],
    operation_id="student_open_lecture_session",
    summary="Open a new lecture study session (T-151)",
    dependencies=[require_role("student")],
)
async def open_lecture_session(
    lecture_id: str,
    payload: LectureSessionOpenRequest | None = None,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    body = payload or LectureSessionOpenRequest()
    result = await LectureSessionService(db).open_session(claims, lecture_id, body)
    return success(result.model_dump(mode="json"))


@student_session_router.post(
    "/{lecture_id}/audio",
    response_model=SuccessEnvelope[LectureAudioCacheRead],
    operation_id="student_request_lecture_audio",
    summary="Request or fetch cached lecture TTS audio (T-153)",
    dependencies=[require_role("student")],
)
async def request_lecture_audio(
    lecture_id: str,
    payload: LectureAudioRequest | None = None,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.features.lectures.lecture_tts import LectureTtsService

    body = payload or LectureAudioRequest()
    result = await LectureTtsService(db).request_or_get(claims, lecture_id, body)
    return success(result.model_dump(mode="json"))


@student_session_router.get(
    "/{lecture_id}/audio/{language}",
    response_model=SuccessEnvelope[LectureAudioCacheRead],
    operation_id="student_get_lecture_audio",
    summary="Get lecture TTS cache status + alignment (T-153)",
    dependencies=[require_role("student")],
)
async def get_lecture_audio(
    lecture_id: str,
    language: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.features.lectures.lecture_tts import LectureTtsService

    result = await LectureTtsService(db).get_status(claims, lecture_id, language)
    return success(result.model_dump(mode="json"))


@student_session_router.get(
    "/{lecture_id}/audio/{language}/download",
    response_model=None,
    operation_id="student_download_lecture_audio",
    summary="302 redirect to 5-min presigned lecture audio URL (T-154)",
    dependencies=[require_role("student")],
)
async def download_lecture_audio(
    lecture_id: str,
    language: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    from app.features.lectures.lecture_tts import LectureTtsService

    url = await LectureTtsService(db).download_url(claims, lecture_id, language)
    return RedirectResponse(url=url, status_code=302)
