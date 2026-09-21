"""Student voice STT service — T-155.

Reuses the M-09 faster-whisper primitive via ``infrastructure.voice.router``.
No lecture ownership checks — this endpoint serves the reusable hybrid input
widget (lecture Q&A, future Flow 5/8/11 chat surfaces).
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.independent_users.repository import IndependentUserRepository
from app.features.student_voice.schemas import VoiceTranscribeRead
from app.features.users.models import UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.voice.router import transcribe as voice_transcribe

logger = structlog.get_logger(__name__)

_MAX_VOICE_AUDIO_BYTES = 10 * 1024 * 1024


class StudentVoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._indep_users = IndependentUserRepository(session)

    async def _require_student(self, claims: dict[str, object]) -> str:
        """Return student user id for school or independent student."""
        role = str(claims.get("role", ""))
        sub = str(claims.get("sub", ""))
        if role == "independent_student":
            user = await self._indep_users.get_by_authentik_id(sub)
            if user is None:
                raise NotFoundError("Student not found")
            return user.id
        if role != UserRole.STUDENT.value:
            raise PermissionDeniedError("Student role required")
        user_s = await self._users.get_by_authentik_id(sub)
        if user_s is None or user_s.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user_s.id

    async def transcribe(
        self,
        claims: dict[str, object],
        audio_bytes: bytes,
        language: str | None,
    ) -> VoiceTranscribeRead:
        student_id = await self._require_student(claims)

        if not audio_bytes:
            raise ValidationError("No audio received")
        if len(audio_bytes) > _MAX_VOICE_AUDIO_BYTES:
            raise ValidationError(
                f"Audio exceeds the {_MAX_VOICE_AUDIO_BYTES // (1024 * 1024)} MB limit"
            )

        transcript = await voice_transcribe(audio_bytes, language=language)
        logger.info(
            "student_voice_transcribed",
            student_user_id=student_id,
            language=language,
            transcript_length=len(transcript),
        )
        return VoiceTranscribeRead(transcript=transcript)
