"""Student voice STT API — T-155 (hybrid input widget)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.student_voice.schemas import VoiceTranscribeRead
from app.features.student_voice.service import StudentVoiceService

router = APIRouter(prefix="/students/me/voice", tags=["student-voice"])


@router.post(
    "/transcribe",
    response_model=SuccessEnvelope[VoiceTranscribeRead],
    operation_id="student_transcribe_voice",
    summary="Transcribe a student voice clip via faster-whisper (T-155)",
    dependencies=[require_role("student")],
)
async def transcribe_voice(
    audio: UploadFile,
    language: str | None = Query(default=None, pattern="^(en|ur|sd|ps)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audio_bytes = await audio.read()
    result = await StudentVoiceService(db).transcribe(claims, audio_bytes, language)
    return success(result.model_dump(mode="json"))
