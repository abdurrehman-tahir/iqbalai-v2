"""Lecture wizard service — steps 1–2 + draft auto-save (T-114).

School teachers only; independent stripped variant is T-125.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.grades.repository import GradeRepository
from app.features.lectures.models import SchoolLectureDraft
from app.features.lectures.repository import LectureDraftRepository
from app.features.lectures.schemas import (
    LectureDraftRead,
    LectureDraftUpsert,
    TeacherOfferingRead,
    WizardCurriculumRead,
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
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


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
