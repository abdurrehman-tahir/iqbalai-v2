"""Lecture wizard service — steps 1–2 + draft auto-save (T-114).

School teachers only; independent stripped variant is T-125.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.grades.cross_grade import (
    assert_cross_grade_access_by_ordinal,
    library_item_visible_for_grade_context,
)
from app.features.grades.repository import GradeRepository
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureDraft,
)
from app.features.lectures.repository import LectureDraftRepository, LectureRepository
from app.features.lectures.schemas import (
    LectureDraftRead,
    LectureDraftUpsert,
    LectureGenerateRead,
    LectureGenerateRequest,
    TeacherOfferingRead,
    TeachingMode,
    WizardCurriculumRead,
    WizardEstimateRead,
    WizardReferenceRead,
    WizardState,
    WizardTopicOption,
    WizardTopicsRead,
)
from app.features.library.school_library_repository import SchoolLibraryRepository
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    SchoolLibraryItem,
)
from app.features.offerings.models import GradeSubjectOffering
from app.features.offerings.repository import OfferingRepository
from app.features.subjects.repository import SubjectRepository
from app.features.teacher_onboarding.repository import TeacherProfileRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

# Heuristic estimate — T-116 will refine with real telemetry.
_BASE_ESTIMATE_SECONDS = 90
_PER_REFERENCE_SECONDS = 25
_MANUAL_MODE_FACTOR = 0.6
_VOICE_MODE_FACTOR = 1.2


def estimate_generation_seconds(*, reference_count: int, teaching_mode: TeachingMode) -> int:
    seconds = _BASE_ESTIMATE_SECONDS + max(0, reference_count) * _PER_REFERENCE_SECONDS
    if teaching_mode == TeachingMode.MANUAL:
        seconds = int(seconds * _MANUAL_MODE_FACTOR)
    elif teaching_mode == TeachingMode.VOICE_ASSISTED:
        seconds = int(seconds * _VOICE_MODE_FACTOR)
    return max(30, seconds)


def _tree_is_degraded(tree: dict[str, Any] | None) -> bool:
    if tree is None:
        return True
    if tree.get("parse_degraded") is True:
        return True
    chapters = tree.get("chapters")
    return not isinstance(chapters, list) or len(chapters) == 0


def flatten_topic_tree(tree: dict[str, Any] | None) -> list[WizardTopicOption]:
    """Walk chapter → section → sub_topic into selectable path labels."""
    if tree is None:
        return []
    chapters = tree.get("chapters")
    if not isinstance(chapters, list):
        return []
    out: list[WizardTopicOption] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_title = str(chapter.get("title") or "").strip()
        if not chapter_title:
            continue
        sections = chapter.get("sections")
        if not isinstance(sections, list) or not sections:
            out.append(WizardTopicOption(path=chapter_title, label=chapter_title))
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_title = str(section.get("title") or "").strip()
            if not section_title:
                continue
            section_path = f"{chapter_title} > {section_title}"
            sub_topics = section.get("sub_topics")
            if not isinstance(sub_topics, list) or not sub_topics:
                out.append(WizardTopicOption(path=section_path, label=section_title))
                continue
            for sub in sub_topics:
                label = str(sub).strip()
                if not label:
                    continue
                out.append(
                    WizardTopicOption(
                        path=f"{section_path} > {label}",
                        label=label,
                    )
                )
    return out


class LectureWizardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._offerings = OfferingRepository(session)
        self._grades = GradeRepository(session)
        self._subjects = SubjectRepository(session)
        self._library = SchoolLibraryRepository(session)
        self._drafts = LectureDraftRepository(session)
        self._lectures = LectureRepository(session)
        self._profiles = TeacherProfileRepository(session)

    async def _require_school_teacher(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.TEACHER:
            raise PermissionDeniedError("Teacher role required")
        if user.school_id is None:
            raise PermissionDeniedError("School teacher context required")
        return user

    async def _require_owned_offering(
        self, teacher: User, offering_id: str
    ) -> GradeSubjectOffering:
        offering = await self._offerings.get_by_id(offering_id)
        if (
            offering is None
            or offering.deleted_at is not None
            or offering.assigned_teacher_id != teacher.id
            or offering.school_id != teacher.school_id
        ):
            raise NotFoundError("Grade-Subject offering not found")
        return offering

    async def list_my_offerings(self, claims: dict[str, object]) -> list[TeacherOfferingRead]:
        teacher = await self._require_school_teacher(claims)
        rows = await self._offerings.list_by_teacher(teacher.id)
        result: list[TeacherOfferingRead] = []
        for offering in rows:
            grade = await self._grades.get_by_id(offering.grade_id)
            subject = await self._subjects.get_by_id(offering.subject_id)
            if grade is None or subject is None:
                continue
            result.append(
                TeacherOfferingRead(
                    id=offering.id,
                    grade_id=offering.grade_id,
                    grade_name=grade.name,
                    grade_level_ordinal=grade.level_ordinal,
                    subject_id=offering.subject_id,
                    subject_name=subject.name,
                    academic_session=offering.academic_session,
                )
            )
        return result

    async def list_curricula_for_offering(
        self, claims: dict[str, object], offering_id: str
    ) -> list[WizardCurriculumRead]:
        teacher = await self._require_school_teacher(claims)
        offering = await self._require_owned_offering(teacher, offering_id)
        grade = await self._grades.get_by_id(offering.grade_id)
        if grade is None:
            raise NotFoundError("Grade not found")

        items, _total = await self._library.list_for_user(
            school_id=teacher.school_id or "",
            user_id=teacher.id,
            subject_id=offering.subject_id,
            grade_level_ordinal=grade.level_ordinal,
            content_type=LibraryContentType.CURRICULUM.value,
        )
        available = [
            item
            for item in items
            if item.ingestion_status == LibraryIngestionStatus.AVAILABLE
            and item.content_type == LibraryContentType.CURRICULUM
        ]

        primary_id = await self._pick_primary_curriculum_id(
            teacher.id, available, grade.level_ordinal
        )
        return [
            WizardCurriculumRead(
                id=item.id,
                title=item.title,
                subject_id=item.subject_id,
                grade_level_ordinal=item.grade_level_ordinal,
                is_primary=item.id == primary_id,
                parse_degraded=_tree_is_degraded(
                    item.topic_tree_jsonb if isinstance(item.topic_tree_jsonb, dict) else None
                ),
                topic_tree_jsonb=(
                    item.topic_tree_jsonb if isinstance(item.topic_tree_jsonb, dict) else None
                ),
            )
            for item in available
        ]

    async def _pick_primary_curriculum_id(
        self,
        teacher_id: str,
        items: list[SchoolLibraryItem],
        grade_ordinal: int,
    ) -> str | None:
        if not items:
            return None
        # Prefer a curriculum the teacher already selected.
        for item in items:
            selection = await self._library.get_selection(item.id, teacher_id)
            if selection is not None:
                return item.id
        # Else prefer exact grade match, else first available.
        exact = [i for i in items if i.grade_level_ordinal == grade_ordinal]
        return (exact[0] if exact else items[0]).id

    async def list_topics_for_curriculum(
        self, claims: dict[str, object], curriculum_id: str, offering_id: str
    ) -> WizardTopicsRead:
        teacher = await self._require_school_teacher(claims)
        await self._require_owned_offering(teacher, offering_id)
        item = await self._library.get_by_id(curriculum_id)
        if (
            item is None
            or item.school_id != teacher.school_id
            or item.content_type != LibraryContentType.CURRICULUM
        ):
            raise NotFoundError("Curriculum not found")
        tree = item.topic_tree_jsonb if isinstance(item.topic_tree_jsonb, dict) else None
        degraded = _tree_is_degraded(tree)
        topics = [] if degraded else flatten_topic_tree(tree)
        return WizardTopicsRead(
            curriculum_id=item.id,
            parse_degraded=degraded,
            topics=topics,
        )

    async def get_draft(self, claims: dict[str, object]) -> LectureDraftRead:
        teacher = await self._require_school_teacher(claims)
        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is None:
            return LectureDraftRead(
                id=None,
                teacher_user_id=teacher.id,
                step=1,
                data={},
                updated_at=None,
            )
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
        teacher = await self._require_school_teacher(claims)
        state = WizardState(step=payload.step, data=payload.data)
        offering_id = state.data.get("grade_subject_offering_id")
        if offering_id is not None and offering_id != "":
            if not isinstance(offering_id, str):
                raise ValidationError("grade_subject_offering_id must be a string")
            await self._require_owned_offering(teacher, offering_id)

        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is None:
            draft = SchoolLectureDraft(
                teacher_user_id=teacher.id,
                wizard_state_jsonb=state.to_jsonb(),
            )
            draft = await self._drafts.create(draft)
        else:
            draft.wizard_state_jsonb = state.to_jsonb()
            draft = await self._drafts.update(draft)

        logger.info(
            "lecture_draft_saved",
            teacher_user_id=teacher.id,
            step=state.step,
            draft_id=draft.id,
        )
        return LectureDraftRead(
            id=draft.id,
            teacher_user_id=draft.teacher_user_id,
            step=state.step,
            data=state.data,
            updated_at=draft.updated_at,
        )

    async def list_references_for_offering(
        self,
        claims: dict[str, object],
        offering_id: str,
        *,
        include_cross_grade: bool = False,
    ) -> list[WizardReferenceRead]:
        teacher = await self._require_school_teacher(claims)
        offering = await self._require_owned_offering(teacher, offering_id)
        grade = await self._grades.get_by_id(offering.grade_id)
        if grade is None:
            raise NotFoundError("Grade not found")

        profile = await self._profiles.get_by_user_id(teacher.id)
        language = profile.language_preference if profile is not None else None

        items, _total = await self._library.list_for_user(
            school_id=teacher.school_id or "",
            user_id=teacher.id,
            subject_id=offering.subject_id,
            grade_level_ordinal=grade.level_ordinal,
            language=language,
            content_type=LibraryContentType.REFERENCE.value,
        )
        available = [
            item
            for item in items
            if item.ingestion_status == LibraryIngestionStatus.AVAILABLE
            and item.content_type == LibraryContentType.REFERENCE
        ]

        result: list[WizardReferenceRead] = []
        for item in available:
            if not library_item_visible_for_grade_context(
                context_ordinal=grade.level_ordinal,
                item_grade_ordinal=item.grade_level_ordinal,
            ):
                continue
            is_cross = (
                item.grade_level_ordinal is not None
                and item.grade_level_ordinal < grade.level_ordinal
            )
            if not include_cross_grade:
                if is_cross:
                    continue
                if (
                    item.grade_level_ordinal is not None
                    and item.grade_level_ordinal != grade.level_ordinal
                ):
                    continue
            result.append(
                WizardReferenceRead(
                    id=item.id,
                    title=item.title,
                    subject_id=item.subject_id,
                    grade_level_ordinal=item.grade_level_ordinal,
                    language=item.language,
                    is_cross_grade=is_cross,
                )
            )
        return result

    def estimate(self, *, reference_count: int, teaching_mode: TeachingMode) -> WizardEstimateRead:
        return WizardEstimateRead(
            estimated_seconds=estimate_generation_seconds(
                reference_count=reference_count,
                teaching_mode=teaching_mode,
            ),
            reference_count=reference_count,
            teaching_mode=teaching_mode,
        )

    async def generate_from_wizard(
        self, claims: dict[str, object], payload: LectureGenerateRequest
    ) -> LectureGenerateRead:
        """Create lecture row at GENERATING; Celery Pattern-S pipeline is T-116."""
        teacher = await self._require_school_teacher(claims)
        offering = await self._require_owned_offering(teacher, payload.grade_subject_offering_id)
        grade = await self._grades.get_by_id(offering.grade_id)
        if grade is None:
            raise NotFoundError("Grade not found")

        curriculum = await self._library.get_by_id(payload.curriculum_id)
        if (
            curriculum is None
            or curriculum.school_id != teacher.school_id
            or curriculum.content_type != LibraryContentType.CURRICULUM
        ):
            raise NotFoundError("Curriculum not found")

        for ref_id in payload.reference_book_ids:
            ref = await self._library.get_by_id(ref_id)
            if (
                ref is None
                or ref.school_id != teacher.school_id
                or ref.content_type != LibraryContentType.REFERENCE
            ):
                raise NotFoundError("Reference book not found")
            if ref.grade_level_ordinal is not None:
                assert_cross_grade_access_by_ordinal(grade.level_ordinal, ref.grade_level_ordinal)
                is_cross = ref.grade_level_ordinal < grade.level_ordinal
                if is_cross and not payload.include_cross_grade:
                    raise ValidationError(
                        "Cross-grade reference selected but include_cross_grade is false"
                    )

        estimated = estimate_generation_seconds(
            reference_count=len(payload.reference_book_ids),
            teaching_mode=payload.teaching_mode,
        )
        lecture = SchoolLecture(
            school_id=teacher.school_id,
            grade_subject_offering_id=offering.id,
            teacher_user_id=teacher.id,
            title=payload.topic[:500],
            topic=payload.topic,
            lecture_type=LectureType.MAIN,
            status=LectureStatus.GENERATING,
        )
        lecture = await self._lectures.create(lecture)

        draft = await self._drafts.get_active_for_teacher(teacher.id)
        if draft is not None:
            draft.wizard_state_jsonb = WizardState(
                step=5,
                data={
                    "grade_subject_offering_id": payload.grade_subject_offering_id,
                    "topic": payload.topic,
                    "curriculum_id": payload.curriculum_id,
                    "reference_book_ids": payload.reference_book_ids,
                    "teaching_mode": payload.teaching_mode.value,
                    "include_cross_grade": payload.include_cross_grade,
                    "lecture_id": lecture.id,
                },
            ).to_jsonb()
            await self._drafts.update(draft)
            await self._drafts.soft_delete(draft)

        logger.info(
            "lecture_generation_requested",
            lecture_id=lecture.id,
            teacher_user_id=teacher.id,
            teaching_mode=payload.teaching_mode.value,
            reference_count=len(payload.reference_book_ids),
        )
        return LectureGenerateRead(
            lecture_id=lecture.id,
            status=LectureStatus.GENERATING.value,
            estimated_seconds=estimated,
        )
