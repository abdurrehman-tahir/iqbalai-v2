"""Independent teacher lecture wizard service — T-125.

Stripped variant of ``service.py``'s ``LectureWizardService``: no Grade-
Subject offering, no curriculum, no auto-quiz, no cross-grade linking, no
per-lecture access control (independents have no students to restrict
access for). Reuses ``TeachingMode``/``WizardEstimateRead``/
``estimate_generation_seconds`` from the school module since those are
already tenant-agnostic shapes with no Grade-Subject coupling.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.audit.actions import LECTURE_CREATED
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.lectures.edit_summary import derive_edit_summary
from app.features.lectures.events import LECTURE_VERSION_CREATED, publish_lecture_event
from app.features.lectures.independent_repository import (
    IndependentLectureDraftRepository,
    IndependentLectureParagraphRepository,
    IndependentLectureRepository,
    IndependentLectureVersionRepository,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    IndependentLectureVersion,
    LectureStatus,
)
from app.features.lectures.schemas import (
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
    ParagraphSourceMetadata,
    TeachingMode,
    VoiceTranscribeRead,
    WizardEstimateRead,
    WizardState,
)
from app.features.lectures.service import estimate_generation_seconds
from app.features.lectures.tiptap import InvalidTipTapDocumentError, extract_plain_text
from app.features.library.independent_personal_models import (
    PersonalContentStatus,
    PersonalContentType,
)
from app.features.library.independent_personal_repository import (
    IndependentPersonalContentRepository,
)
from app.infrastructure.audit.log import audit
from app.infrastructure.storage.client import download_bytes
from app.infrastructure.voice.router import transcribe as voice_transcribe

_MAX_VOICE_AUDIO_BYTES = 10 * 1024 * 1024

logger = structlog.get_logger(__name__)


class IndependentLectureWizardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = IndependentUserRepository(session)
        self._drafts = IndependentLectureDraftRepository(session)
        self._lectures = IndependentLectureRepository(session)
        self._paragraphs = IndependentLectureParagraphRepository(session)
        self._versions = IndependentLectureVersionRepository(session)
        self._personal_content = IndependentPersonalContentRepository(session)

    async def _require_independent_teacher(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != IndependentUserRole.INDEPENDENT_TEACHER:
            raise PermissionDeniedError("Independent teacher role required")
        return user

    async def _require_owned_lecture(
        self, teacher: IndependentUser, lecture_id: str
    ) -> IndependentLecture:
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None or lecture.teacher_user_id != teacher.id:
            raise NotFoundError("Lecture not found")
        return lecture

    async def list_my_references(
        self, claims: dict[str, object]
    ) -> list[IndependentWizardReferenceRead]:
        """Step 3: only the teacher's own private references — no school library."""
        teacher = await self._require_independent_teacher(claims)
        items = await self._personal_content.list_for_user(
            teacher.id, content_type=PersonalContentType.REFERENCE.value
        )
        return [
            IndependentWizardReferenceRead(id=item.id, title=item.title)
            for item in items
            if item.status == PersonalContentStatus.AVAILABLE
        ]

    async def get_draft(self, claims: dict[str, object]) -> LectureDraftRead:
        teacher = await self._require_independent_teacher(claims)
        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is None:
            return LectureDraftRead(teacher_user_id=teacher.id, step=1, data={})
        state = WizardState.from_jsonb(
            draft.wizard_state_jsonb if isinstance(draft.wizard_state_jsonb, dict) else {}
        )
        return LectureDraftRead(
            id=draft.id,
            teacher_user_id=draft.teacher_user_id,
            step=state.step,
            data=state.data,
            updated_at=draft.updated_at,
        )

    async def upsert_draft(
        self, claims: dict[str, object], payload: LectureDraftUpsert
    ) -> LectureDraftRead:
        teacher = await self._require_independent_teacher(claims)
        state = WizardState(step=payload.step, data=payload.data)
        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is None:
            draft = IndependentLectureDraft(
                teacher_user_id=teacher.id, wizard_state_jsonb=state.to_jsonb()
            )
            draft = await self._drafts.create(draft)
        else:
            draft.wizard_state_jsonb = state.to_jsonb()
            draft = await self._drafts.update(draft)
        return LectureDraftRead(
            id=draft.id,
            teacher_user_id=draft.teacher_user_id,
            step=payload.step,
            data=payload.data,
            updated_at=draft.updated_at,
        )

    def estimate(self, *, reference_count: int, teaching_mode: TeachingMode) -> WizardEstimateRead:
        return WizardEstimateRead(
            estimated_seconds=estimate_generation_seconds(
                reference_count=reference_count, teaching_mode=teaching_mode
            ),
            reference_count=reference_count,
            teaching_mode=teaching_mode,
        )

    async def generate_from_wizard(
        self, claims: dict[str, object], payload: IndependentLectureGenerateRequest
    ) -> LectureGenerateRead:
        """Create lecture at GENERATING and enqueue the independent Celery task."""
        teacher = await self._require_independent_teacher(claims)

        for content_id in payload.reference_content_ids:
            item = await self._personal_content.get_by_id(content_id)
            if item is None or item.user_id != teacher.id:
                raise NotFoundError("Reference not found")

        estimated = estimate_generation_seconds(
            reference_count=len(payload.reference_content_ids),
            teaching_mode=payload.teaching_mode,
        )
        lecture = IndependentLecture(
            teacher_user_id=teacher.id,
            title=payload.topic[:500],
            topic=payload.topic,
            status=LectureStatus.GENERATING,
        )
        lecture = await self._lectures.create(lecture)
        await audit(
            session=self._session,
            action=LECTURE_CREATED,
            actor_id=teacher.id,
            actor_role=teacher.role.value,
            target_type="lecture",
            target_id=lecture.id,
            school_id=None,
            metadata={"topic": payload.topic[:200]},
        )

        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is not None:
            await self._drafts.soft_delete(draft)

        from app.features.lectures.independent_tasks import generate_independent_lecture

        generate_independent_lecture.apply_async(
            kwargs={
                "lecture_id": lecture.id,
                "user_id": teacher.id,
                "topic": payload.topic,
                "reference_content_ids": list(payload.reference_content_ids),
                "teaching_mode": payload.teaching_mode.value,
                "target_language": "en",
            }
        )

        logger.info(
            "independent_lecture_generation_requested",
            lecture_id=lecture.id,
            teacher_user_id=teacher.id,
            teaching_mode=payload.teaching_mode.value,
            reference_count=len(payload.reference_content_ids),
        )
        return LectureGenerateRead(
            lecture_id=lecture.id,
            status=lecture.status.value,
            estimated_seconds=estimated,
        )

    async def get_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> IndependentLectureRead:
        """Minimal status for the frontend to poll (no WS stream in this variant)."""
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        return IndependentLectureRead(
            id=lecture.id,
            status=lecture.status.value,
            title=lecture.title,
            current_version_id=lecture.current_version_id,
        )

    async def get_lecture_paragraphs(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[LectureParagraphRead]:
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        if lecture.current_version_id is None:
            return []

        paragraphs = await self._paragraphs.list_by_version(lecture.current_version_id)
        return [
            LectureParagraphRead(
                ordinal=p.ordinal,
                text=p.text,
                **ParagraphSourceMetadata.from_jsonb(p.source_metadata_jsonb).model_dump(
                    exclude={"chunk_id"}
                ),
            )
            for p in paragraphs
        ]

    @staticmethod
    def _to_version_read(version: IndependentLectureVersion) -> LectureVersionRead:
        return LectureVersionRead(
            id=version.id,
            lecture_id=version.lecture_id,
            version=version.version,
            content_jsonb=version.content_jsonb,
            body=version.body,
            scores_jsonb=version.scores_jsonb,
            topic_relevance_pct=(
                float(version.topic_relevance_pct)
                if version.topic_relevance_pct is not None
                else None
            ),
            originality_score=(
                float(version.originality_score) if version.originality_score is not None else None
            ),
            edit_summary=version.edit_summary,
            created_at=version.created_at,
        )

    async def get_current_lecture_version(
        self, claims: dict[str, object], lecture_id: str
    ) -> LectureVersionRead:
        """Loads the editor's initial content (T-130)."""
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        if lecture.current_version_id is None:
            raise NotFoundError("Lecture has no version yet")
        version = await self._versions.get_by_id(lecture.current_version_id)
        if version is None:
            raise NotFoundError("Lecture version not found")
        return self._to_version_read(version)

    async def save_lecture_version(
        self,
        claims: dict[str, object],
        lecture_id: str,
        payload: LectureVersionSaveRequest,
        *,
        extra_annotations: list[str] | None = None,
    ) -> LectureVersionRead:
        """Save an edit as a new immutable version (T-130, #29-#31).

        Mirrors ``LectureWizardService.save_lecture_version`` — no school_id,
        no Grade-Subject (independent teachers have neither, per §3.16).
        """
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        if lecture.status not in (LectureStatus.READY_FOR_EDIT, LectureStatus.READY_FOR_PUBLISH):
            raise ValidationError(f"Lecture is not editable in status {lecture.status.value}")

        latest = await self._versions.get_latest_for_lecture(lecture.id)
        if latest is None:
            raise NotFoundError("Lecture has no existing version to edit")

        try:
            body = extract_plain_text(payload.content_jsonb)
        except InvalidTipTapDocumentError as exc:
            raise ValidationError(str(exc)) from exc
        if not body:
            raise ValidationError("Lecture content cannot be empty")

        merged_annotations = list(extra_annotations or [])
        if payload.used_voice_edit:
            merged_annotations.append("Applied voice edit")
        annotations = derive_edit_summary(
            previous_body=latest.body,
            new_body=body,
            extra_annotations=merged_annotations,
        )

        version = IndependentLectureVersion(
            lecture_id=lecture.id,
            version=latest.version + 1,
            body=body,
            content_jsonb=payload.content_jsonb,
            edit_summary=annotations,
        )
        lecture.current_version_id = version.id
        version = await self._versions.create(version)

        await publish_lecture_event(
            event_type=LECTURE_VERSION_CREATED,
            payload={
                "lecture_id": lecture.id,
                "version_id": version.id,
                "version": version.version,
                "teacher_user_id": teacher.id,
                "tenant_type": "independent",
                "is_autosave": payload.is_autosave,
            },
        )
        logger.info(
            "lecture_version_saved",
            lecture_id=lecture.id,
            version_id=version.id,
            version=version.version,
            is_autosave=payload.is_autosave,
        )
        return self._to_version_read(version)

    async def transcribe_voice_edit(
        self,
        claims: dict[str, object],
        lecture_id: str,
        audio_bytes: bytes,
        language: str | None,
    ) -> VoiceTranscribeRead:
        """Voice dictation STT (T-131, #29). Mirrors the school variant."""
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        if lecture.status not in (LectureStatus.READY_FOR_EDIT, LectureStatus.READY_FOR_PUBLISH):
            raise ValidationError(f"Lecture is not editable in status {lecture.status.value}")

        if not audio_bytes:
            raise ValidationError("No audio received")
        if len(audio_bytes) > _MAX_VOICE_AUDIO_BYTES:
            raise ValidationError(
                f"Audio exceeds the {_MAX_VOICE_AUDIO_BYTES // (1024 * 1024)} MB limit"
            )

        transcript = await voice_transcribe(audio_bytes, language=language)
        logger.info(
            "lecture_voice_edit_transcribed",
            lecture_id=lecture.id,
            language=language,
            transcript_length=len(transcript),
        )
        return VoiceTranscribeRead(transcript=transcript)

    async def upload_lecture_image(
        self,
        claims: dict[str, object],
        lecture_id: str,
        data: bytes,
        filename: str,
    ) -> LectureImageUploadRead:
        """Drag-drop image upload (T-132, #30). No AI diagram suggestion for
        independent teachers — their personal-reference-content model has no
        page-chunked structure to draw suggestions from (school-tenant only).
        """
        teacher = await self._require_independent_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        if lecture.status not in (LectureStatus.READY_FOR_EDIT, LectureStatus.READY_FOR_PUBLISH):
            raise ValidationError(f"Lecture is not editable in status {lecture.status.value}")

        profile = get_profile("lecture_image")
        try:
            # UploadRecord lives in the school schema only — independent
            # uploads reuse it the same way independent_personal_service.py
            # already does, scoping "school_id" to the independent user's own
            # id instead (per-user, not per-school dedup/scoping).
            result = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=teacher.id,
                uploaded_by=teacher.id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        return LectureImageUploadRead(
            image_id=result.upload_id,
            image_url=(
                f"/api/v1/independent/teachers/me/lectures/{lecture.id}/images/{result.upload_id}"
            ),
        )

    async def get_lecture_image(
        self, claims: dict[str, object], lecture_id: str, image_id: str
    ) -> tuple[bytes, str]:
        teacher = await self._require_independent_teacher(claims)
        await self._require_owned_lecture(teacher, lecture_id)

        record = await self._session.get(UploadRecord, image_id)
        if record is None or record.profile != "lecture_image" or record.school_id != teacher.id:
            raise NotFoundError("Image not found")
        data = download_bytes(record.bucket, record.minio_key)
        return data, record.filename
