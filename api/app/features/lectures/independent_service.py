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

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.lectures.independent_repository import (
    IndependentLectureDraftRepository,
    IndependentLectureParagraphRepository,
    IndependentLectureRepository,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    LectureStatus,
)
from app.features.lectures.schemas import (
    IndependentLectureGenerateRequest,
    IndependentLectureRead,
    IndependentWizardReferenceRead,
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureParagraphRead,
    ParagraphSourceMetadata,
    TeachingMode,
    WizardEstimateRead,
    WizardState,
)
from app.features.lectures.service import estimate_generation_seconds
from app.features.library.independent_personal_models import (
    PersonalContentStatus,
    PersonalContentType,
)
from app.features.library.independent_personal_repository import (
    IndependentPersonalContentRepository,
)

logger = structlog.get_logger(__name__)


class IndependentLectureWizardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = IndependentUserRepository(session)
        self._drafts = IndependentLectureDraftRepository(session)
        self._lectures = IndependentLectureRepository(session)
        self._paragraphs = IndependentLectureParagraphRepository(session)
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
