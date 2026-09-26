"""Student question image ingest — T-166 (`student_question_image` profile).

Authenticated student endpoint that reuses the shared MinIO upload pipeline
(ARCH §11.19). Does not invent a parallel storage framework.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import (
    STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION,
    get_profile,
)
from app.features.student_questions.schemas import StudentQuestionImageUploadRead
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

_MIME_BY_EXT: dict[str, Literal["image/jpeg", "image/png", "image/webp"]] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _guess_mime(filename: str, data: bytes) -> Literal["image/jpeg", "image/png", "image/webp"]:
    lower = filename.lower()
    for ext, mime in _MIME_BY_EXT.items():
        if lower.endswith(ext):
            return mime
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValidationError("Format not supported — use JPEG, PNG, or WEBP")


def _tenant_scope_id(student: User) -> str:
    """Per-tenant MinIO scope: school_id for school students, else user id."""
    if student.school_id:
        return student.school_id
    return student.id


class StudentQuestionImageService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def upload_image(
        self,
        claims: dict[str, object],
        data: bytes,
        filename: str,
        *,
        already_attached: int = 0,
    ) -> StudentQuestionImageUploadRead:
        """Ingest one student_question_image; returns MinIO key for attached_images[]."""
        student = await self._require_student(claims)

        if already_attached >= STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION:
            raise ValidationError(
                f"Max {STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION} images per question"
            )

        # Reject GIF / other unsupported types early (magic also rejects in pipeline).
        if filename.lower().endswith(".gif") or data[:6] in (b"GIF87a", b"GIF89a"):
            raise ValidationError("Format not supported — use JPEG, PNG, or WEBP")

        mime = _guess_mime(filename, data)
        profile = get_profile("student_question_image")
        if mime not in profile.allowed_mime_types:
            raise ValidationError("Format not supported — use JPEG, PNG, or WEBP")

        try:
            result = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=_tenant_scope_id(student),
                uploaded_by=student.id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # Re-fetch size after EXIF strip / dedup via status URL is awkward —
        # return post-pipeline size from the UploadRecord id.
        from app.features.files.models import UploadRecord

        record = await self._session.get(UploadRecord, result.upload_id)
        if record is None:
            raise ValidationError("Upload failed")

        return StudentQuestionImageUploadRead(
            upload_id=result.upload_id,
            storage_key=record.minio_key,
            mime_type=mime,
            size_bytes=record.size_bytes,
            retention_days=profile.retention_days or 365,
        )
