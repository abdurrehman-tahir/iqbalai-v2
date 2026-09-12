"""Lecture wizard service — steps 1–2 + draft auto-save (T-114).

School teachers only; independent stripped variant is T-125.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.audit.actions import (
    LECTURE_ACCESS_CHANGED,
    LECTURE_ACCESS_OVERRIDDEN,
    LECTURE_CREATED,
    LECTURE_LINKED,
)
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.grades.cross_grade import (
    assert_cross_grade_access_by_ordinal,
    library_item_visible_for_grade_context,
)
from app.features.grades.repository import GradeRepository
from app.features.lectures.edit_summary import derive_edit_summary
from app.features.lectures.effort import compute_effort_score
from app.features.lectures.events import LECTURE_VERSION_CREATED, publish_lecture_event
from app.features.lectures.images import (
    DiagramRenderError,
    IndexedChunk,
    render_pdf_page_to_png,
    suggest_diagrams_from_chunks,
)
from app.features.lectures.models import (
    LectureAssignmentScope as AssignmentScopeModel,
)
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureAssignment,
    SchoolLectureDraft,
    SchoolLectureEditSession,
    SchoolLectureLink,
    SchoolLectureVersion,
)
from app.features.lectures.repository import (
    LectureAssignmentRepository,
    LectureDraftRepository,
    LectureEditSessionRepository,
    LectureLinkRepository,
    LectureParagraphRepository,
    LectureRepository,
    LectureVersionRepository,
)
from app.features.lectures.schemas import (
    DiagramSuggestion,
    DiagramSuggestionAccept,
    DiagramSuggestionsRead,
    EditSessionHeartbeatRequest,
    EditSessionRead,
    EditSessionStartRequest,
    LectureAccessSettingsRead,
    LectureAccessSettingsUpdate,
    LectureAssignmentRead,
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
    ParagraphSourceMetadata,
    RosterSectionRead,
    RosterStudentRead,
    TeacherOfferingRead,
    TeacherTips,
    TeachingMode,
    VoiceTranscribeRead,
    WizardCurriculumRead,
    WizardEstimateRead,
    WizardReferenceRead,
    WizardState,
    WizardTopicOption,
    WizardTopicsRead,
)
from app.features.lectures.schemas import (
    LectureAssignmentScope as AssignmentScopeSchema,
)
from app.features.lectures.tiptap import InvalidTipTapDocumentError, extract_plain_text
from app.features.library.school_library_repository import SchoolLibraryRepository
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    SchoolLibraryItem,
    SchoolLibraryItemChunk,
)
from app.features.offerings.models import GradeSubjectOffering
from app.features.offerings.repository import OfferingRepository
from app.features.sections.repository import SectionRepository
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.subjects.repository import SubjectRepository
from app.features.teacher_onboarding.repository import TeacherProfileRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.storage.client import download_bytes
from app.infrastructure.voice.router import transcribe as voice_transcribe

logger = structlog.get_logger(__name__)

# Heuristic estimate — T-116 will refine with real telemetry.
_BASE_ESTIMATE_SECONDS = 90
_PER_REFERENCE_SECONDS = 25
_MANUAL_MODE_FACTOR = 0.6
_VOICE_MODE_FACTOR = 1.2

# Matches ws_voice_router.py's _MAX_TURN_AUDIO_BYTES (T-121 precedent) — one
# dictated utterance, not a whole conversation.
_MAX_VOICE_AUDIO_BYTES = 10 * 1024 * 1024


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
        self._versions = LectureVersionRepository(session)
        self._edit_sessions = LectureEditSessionRepository(session)
        self._paragraphs = LectureParagraphRepository(session)
        self._links = LectureLinkRepository(session)
        self._assignments = LectureAssignmentRepository(session)
        self._enrollments = StudentEnrollmentRepository(session)
        self._sections = SectionRepository(session)
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

    async def _require_owned_lecture(self, teacher: User, lecture_id: str) -> SchoolLecture:
        """Ownership check mirrors the WS route (T-117): same school, owning teacher.

        T-123 broadens this to real per-lecture ACLs.
        """
        lecture = await self._lectures.get_by_id(lecture_id)
        if (
            lecture is None
            or lecture.school_id != teacher.school_id
            or lecture.teacher_user_id != teacher.id
        ):
            raise NotFoundError("Lecture not found")
        return lecture

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
        """Create lecture at GENERATING and enqueue Pattern-S Celery generation."""
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
        await audit(
            session=self._session,
            action=LECTURE_CREATED,
            actor_id=teacher.id,
            actor_role=teacher.role.value,
            target_type="lecture",
            target_id=lecture.id,
            school_id=teacher.school_id,
            metadata={"topic": payload.topic[:200]},
        )

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

        from app.features.lectures.tasks import generate_lecture

        generate_lecture.apply_async(
            kwargs={
                "lecture_id": lecture.id,
                "school_id": teacher.school_id,
                "topic": payload.topic,
                "curriculum_id": payload.curriculum_id,
                "reference_book_ids": list(payload.reference_book_ids),
                "teaching_mode": payload.teaching_mode.value,
                "teacher_user_id": teacher.id,
                "target_language": "en",
            }
        )

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

    async def get_lecture_paragraphs(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[LectureParagraphRead]:
        """Current-version paragraphs with source attribution (T-118).

        Ownership check mirrors the WS route (T-117): same school, owning
        teacher — T-123 broadens this to real per-lecture ACLs.
        """
        teacher = await self._require_school_teacher(claims)
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

    async def get_lecture_teacher_tips(
        self, claims: dict[str, object], lecture_id: str
    ) -> LectureTeacherTipsRead:
        """Teacher-facing delivery tips / technique demo / real-world examples (T-124).

        ``pending`` until the second, separate LLM call (chained after generation)
        completes or silently fails — this is supplementary content, never a
        reason to error the lecture detail view.
        """
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        if lecture.current_version_id is None:
            return LectureTeacherTipsRead(lecture_id=lecture.id, status="pending", tips=None)

        version = await self._versions.get_by_id(lecture.current_version_id)
        if version is None or version.teacher_tips_jsonb is None:
            return LectureTeacherTipsRead(lecture_id=lecture.id, status="pending", tips=None)

        tips = TeacherTips.from_jsonb(version.teacher_tips_jsonb)
        return LectureTeacherTipsRead(lecture_id=lecture.id, status="ready", tips=tips)

    @staticmethod
    def _to_version_read(version: SchoolLectureVersion) -> LectureVersionRead:
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
        teacher = await self._require_school_teacher(claims)
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

        Every save — manual or (frontend-)debounced auto-save — creates a new
        ``lecture_versions`` row; the prior row is never touched (§4.18). Server
        re-validates teacher ownership of the lecture's Grade-Subject via
        ``_require_owned_lecture`` (the same check every other mutation on this
        lecture uses) — the frontend's READY_FOR_EDIT gate is not trusted alone.
        ``extra_annotations`` lets T-131 (voice) / T-132 (image) contribute their
        own edit_summary entries without duplicating this method.
        """
        teacher = await self._require_school_teacher(claims)
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

        version = SchoolLectureVersion(
            lecture_id=lecture.id,
            version=latest.version + 1,
            body=body,
            content_jsonb=payload.content_jsonb,
            edit_summary=annotations,
        )
        lecture.current_version_id = version.id
        version = await self._versions.create(version)

        if payload.edit_session_id:
            await self._link_edit_session(
                payload.edit_session_id, teacher_user_id=teacher.id, version_id=version.id
            )

        await publish_lecture_event(
            event_type=LECTURE_VERSION_CREATED,
            payload={
                "lecture_id": lecture.id,
                "version_id": version.id,
                "version": version.version,
                "school_id": teacher.school_id,
                "teacher_user_id": teacher.id,
                "tenant_type": "school",
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

        # T-134 (#32): every save scores the new version asynchronously.
        from app.features.lectures.tasks import score_lecture_version

        score_lecture_version.apply_async(
            kwargs={
                "lecture_id": lecture.id,
                "school_id": teacher.school_id,
                "version_id": version.id,
            }
        )

        return self._to_version_read(version)

    async def _link_edit_session(
        self, edit_session_id: str, *, teacher_user_id: str, version_id: str
    ) -> None:
        """Best-effort — an invalid/foreign session id must never fail the save
        itself; effort data is a scoring input (T-134), not save-path-critical.
        """
        edit_session = await self._edit_sessions.get_by_id(edit_session_id)
        if edit_session is None or edit_session.teacher_user_id != teacher_user_id:
            logger.warning(
                "lecture_edit_session_link_skipped",
                edit_session_id=edit_session_id,
                reason="not_found_or_not_owned",
            )
            return
        edit_session.lecture_version_id = version_id
        await self._edit_sessions.update(edit_session)

    @staticmethod
    def _to_edit_session_read(edit_session: SchoolLectureEditSession) -> EditSessionRead:
        return EditSessionRead(
            id=edit_session.id,
            active_ms=edit_session.active_ms,
            edits_count=edit_session.edits_count,
            char_delta=edit_session.char_delta,
            started_at=edit_session.started_at,
            ended_at=edit_session.ended_at,
            effort_score=compute_effort_score(
                active_ms=edit_session.active_ms, char_delta=edit_session.char_delta
            ),
        )

    async def start_edit_session(
        self, claims: dict[str, object], payload: EditSessionStartRequest
    ) -> EditSessionRead:
        """Opens a new effort-tracking session (T-133, #31).

        Not tied to a version yet — ``save_lecture_version`` links it once the
        teacher's first save in this session completes (see ``_link_edit_session``).
        A teacher may have several concurrent/sequential sessions against the
        same in-progress draft before saving (model docstring, T-129).
        """
        teacher = await self._require_school_teacher(claims)
        await self._require_owned_lecture(teacher, payload.lecture_id)

        edit_session = SchoolLectureEditSession(teacher_user_id=teacher.id)
        edit_session = await self._edit_sessions.create(edit_session)
        return self._to_edit_session_read(edit_session)

    async def _require_owned_edit_session(
        self, claims: dict[str, object], edit_session_id: str
    ) -> SchoolLectureEditSession:
        teacher = await self._require_school_teacher(claims)
        edit_session = await self._edit_sessions.get_by_id(edit_session_id)
        if edit_session is None or edit_session.teacher_user_id != teacher.id:
            raise NotFoundError("Edit session not found")
        return edit_session

    async def heartbeat_edit_session(
        self,
        claims: dict[str, object],
        edit_session_id: str,
        payload: EditSessionHeartbeatRequest,
    ) -> EditSessionRead:
        """30s heartbeat (T-133, #31) — the client sends cumulative totals, not
        deltas, so a retried heartbeat (network hiccup) is a safe no-op overwrite
        rather than double-counting.
        """
        edit_session = await self._require_owned_edit_session(claims, edit_session_id)
        if edit_session.ended_at is not None:
            raise ValidationError("Edit session has already ended")
        edit_session.active_ms = payload.active_ms
        edit_session.edits_count = payload.edits_count
        edit_session.char_delta = payload.char_delta
        edit_session = await self._edit_sessions.update(edit_session)
        return self._to_edit_session_read(edit_session)

    async def end_edit_session(
        self,
        claims: dict[str, object],
        edit_session_id: str,
        payload: EditSessionHeartbeatRequest,
    ) -> EditSessionRead:
        """Final cumulative totals + ``ended_at`` (tab close / editor unmount)."""
        edit_session = await self._require_owned_edit_session(claims, edit_session_id)
        if edit_session.ended_at is None:
            edit_session.active_ms = payload.active_ms
            edit_session.edits_count = payload.edits_count
            edit_session.char_delta = payload.char_delta
            edit_session.ended_at = datetime.now(timezone.utc)
            edit_session = await self._edit_sessions.update(edit_session)
        return self._to_edit_session_read(edit_session)

    async def transcribe_voice_edit(
        self,
        claims: dict[str, object],
        lecture_id: str,
        audio_bytes: bytes,
        language: str | None,
    ) -> VoiceTranscribeRead:
        """Voice dictation STT (T-131, #29). Reuses the M-09 STT primitive only —

        NOT T-121's conversational WS/LLM edit-interpretation pipeline. The
        teacher dictates the content itself; the frontend inserts the returned
        transcript at the cursor or over the current selection (TipTap's
        ``insertContent`` already replaces a selection when one exists — no
        server-side insert-vs-replace branching needed) and saves normally
        through ``save_lecture_version`` with ``used_voice_edit=True``.
        """
        teacher = await self._require_school_teacher(claims)
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
        """Drag-drop image upload into the TipTap editor (T-132, #30).

        Display-only per ARCH §11.19/§11.12 — no ingestion_task_name, no OCR.
        """
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        if lecture.status not in (LectureStatus.READY_FOR_EDIT, LectureStatus.READY_FOR_PUBLISH):
            raise ValidationError(f"Lecture is not editable in status {lecture.status.value}")

        profile = get_profile("lecture_image")
        try:
            result = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=teacher.school_id,
                uploaded_by=teacher.id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        return LectureImageUploadRead(
            image_id=result.upload_id,
            image_url=f"/api/v1/teachers/me/lectures/{lecture.id}/images/{result.upload_id}",
        )

    async def get_lecture_image(
        self, claims: dict[str, object], lecture_id: str, image_id: str
    ) -> tuple[bytes, str]:
        """Streams an uploaded lecture image back (bytes, filename) for `<img src>`."""
        teacher = await self._require_school_teacher(claims)
        await self._require_owned_lecture(teacher, lecture_id)

        record = await self._session.get(UploadRecord, image_id)
        if (
            record is None
            or record.profile != "lecture_image"
            or record.school_id != teacher.school_id
        ):
            raise NotFoundError("Image not found")
        data = download_bytes(record.bucket, record.minio_key)
        return data, record.filename

    async def suggest_diagrams(
        self, claims: dict[str, object], lecture_id: str
    ) -> DiagramSuggestionsRead:
        """AI-flagged reference-book pages likely containing a relevant diagram
        (T-132, #30). Reuses only the reference chunks this lecture's v1 draft
        actually cited — no new ingestion pass over the reference library.
        """
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        v1 = await self._versions.get_first_for_lecture(lecture.id)
        if v1 is None:
            return DiagramSuggestionsRead(suggestions=[])

        paragraphs = await self._paragraphs.list_by_version(v1.id)
        book_names: set[str] = set()
        for p in paragraphs:
            meta = ParagraphSourceMetadata.from_jsonb(p.source_metadata_jsonb)
            if meta.tier.value == "reference" and meta.book_name:
                book_names.add(meta.book_name)
        if not book_names:
            return DiagramSuggestionsRead(suggestions=[])

        items_result = await self._session.execute(
            select(SchoolLibraryItem).where(
                SchoolLibraryItem.school_id == teacher.school_id,
                SchoolLibraryItem.title.in_(book_names),
                SchoolLibraryItem.deleted_at.is_(None),
            )
        )
        items = list(items_result.scalars().all())
        if not items:
            return DiagramSuggestionsRead(suggestions=[])

        item_by_id = {item.id: item for item in items}
        chunks_result = await self._session.execute(
            select(SchoolLibraryItemChunk)
            .where(SchoolLibraryItemChunk.library_item_id.in_(item_by_id.keys()))
            .order_by(SchoolLibraryItemChunk.library_item_id, SchoolLibraryItemChunk.chunk_index)
            .limit(40)
        )
        chunk_rows = list(chunks_result.scalars().all())

        indexed_chunks: list[IndexedChunk] = [
            {
                "index": i,
                "book_name": item_by_id[c.library_item_id].title,
                "page_number": c.page_number or 1,
                "text": c.chunk_text,
                "library_item_id": c.library_item_id,
            }
            for i, c in enumerate(chunk_rows)
        ]
        flagged = await suggest_diagrams_from_chunks(topic=lecture.topic, chunks=indexed_chunks)

        suggestions: list[DiagramSuggestion] = []
        by_index: dict[int, IndexedChunk] = {c["index"]: c for c in indexed_chunks}
        for flag in flagged:
            idx = flag.get("index")
            source = by_index.get(idx) if isinstance(idx, int) else None
            if source is None:
                continue
            suggestions.append(
                DiagramSuggestion(
                    library_item_id=source["library_item_id"],
                    book_name=source["book_name"],
                    page_number=source["page_number"],
                    reason=str(flag.get("reason", "")),
                )
            )
        return DiagramSuggestionsRead(suggestions=suggestions[:3])

    async def accept_diagram_suggestion(
        self, claims: dict[str, object], lecture_id: str, payload: DiagramSuggestionAccept
    ) -> LectureImageUploadRead:
        """Renders the named reference-book page and stores it as a lecture image
        (via the same lecture_image pipeline as a direct upload) — the frontend
        then inserts it identically either way.
        """
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        item = await self._library.get_by_id(payload.library_item_id)
        if item is None or item.school_id != teacher.school_id:
            raise NotFoundError("Reference book not found")

        source_profile = get_profile("school_library_content")
        try:
            pdf_bytes = download_bytes(source_profile.bucket, item.storage_key)
            png_bytes = render_pdf_page_to_png(pdf_bytes, payload.page_number)
        except DiagramRenderError as exc:
            raise ValidationError(str(exc)) from exc

        image_profile = get_profile("lecture_image")
        try:
            result = await run_upload_pipeline(
                data=png_bytes,
                filename=f"{item.title[:80]}-page-{payload.page_number}.png",
                profile=image_profile,
                session=self._session,
                school_id=teacher.school_id,
                uploaded_by=teacher.id,
                skip_magic_check=True,  # server-rendered PNG, not a user-supplied file
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        logger.info(
            "lecture_diagram_accepted",
            lecture_id=lecture.id,
            library_item_id=item.id,
            page_number=payload.page_number,
        )
        return LectureImageUploadRead(
            image_id=result.upload_id,
            image_url=f"/api/v1/teachers/me/lectures/{lecture.id}/images/{result.upload_id}",
        )

    async def _read_link(self, link: SchoolLectureLink) -> LectureLinkRead | None:
        offering = await self._offerings.get_by_id(link.target_grade_subject_offering_id)
        if offering is None:
            return None
        grade = await self._grades.get_by_id(offering.grade_id)
        subject = await self._subjects.get_by_id(offering.subject_id)
        if grade is None or subject is None:
            return None
        return LectureLinkRead(
            id=link.id,
            lecture_id=link.lecture_id,
            target_grade_subject_offering_id=offering.id,
            target_grade_id=grade.id,
            target_grade_name=grade.name,
            target_grade_level_ordinal=grade.level_ordinal,
            target_subject_id=offering.subject_id,
            target_subject_name=subject.name,
            created_at=link.created_at,
        )

    async def list_lecture_links(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[LectureLinkRead]:
        """Links rendered in the lecture detail view (T-122, #21)."""
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)

        links = await self._links.list_by_lecture(lecture.id)
        result: list[LectureLinkRead] = []
        for link in links:
            read = await self._read_link(link)
            if read is not None:
                result.append(read)
        return result

    async def link_lecture(
        self, claims: dict[str, object], lecture_id: str, payload: LectureLinkCreate
    ) -> LectureLinkRead:
        """Self-link a lecture into another Grade-Subject offering the teacher owns.

        Auto-approved (no admin-approval workflow — see T-122 scope note). The
        unidirectional cross-grade rule (target grade <= source grade) is enforced
        by reusing T-047's ``assert_cross_grade_access_by_ordinal`` guard, not
        reimplemented here. Cross-subject linking is allowed implicitly: the
        target offering's subject need not match the source lecture's subject.
        """
        teacher = await self._require_school_teacher(claims)
        lecture = await self._require_owned_lecture(teacher, lecture_id)
        if lecture.grade_subject_offering_id is None:
            raise ValidationError("Lecture has no source Grade-Subject offering to link from")

        source_offering = await self._offerings.get_by_id(lecture.grade_subject_offering_id)
        if source_offering is None:
            raise NotFoundError("Source Grade-Subject offering not found")
        source_grade = await self._grades.get_by_id(source_offering.grade_id)
        if source_grade is None:
            raise NotFoundError("Source grade not found")

        target_offering = await self._require_owned_offering(
            teacher, payload.target_grade_subject_offering_id
        )
        if target_offering.id == source_offering.id:
            raise ValidationError("Cannot link a lecture to its own Grade-Subject offering")
        target_grade = await self._grades.get_by_id(target_offering.grade_id)
        if target_grade is None:
            raise NotFoundError("Target grade not found")

        assert_cross_grade_access_by_ordinal(source_grade.level_ordinal, target_grade.level_ordinal)

        existing = await self._links.get_existing(lecture.id, target_offering.id)
        if existing is not None:
            raise ValidationError("Lecture is already linked to this Grade-Subject offering")

        link = SchoolLectureLink(
            lecture_id=lecture.id,
            target_grade_subject_offering_id=target_offering.id,
            created_by_user_id=teacher.id,
        )
        link = await self._links.create(link)
        await audit(
            session=self._session,
            action=LECTURE_LINKED,
            actor_id=teacher.id,
            actor_role=teacher.role.value,
            target_type="lecture",
            target_id=lecture.id,
            school_id=teacher.school_id,
            metadata={"target_grade_subject_offering_id": target_offering.id},
        )

        logger.info(
            "lecture_link_created",
            lecture_id=lecture.id,
            target_grade_subject_offering_id=target_offering.id,
            teacher_user_id=teacher.id,
        )
        read = await self._read_link(link)
        if read is None:
            raise NotFoundError("Target Grade-Subject offering not found")
        return read

    async def _read_access_settings(
        self, lecture_id: str, rows: list[SchoolLectureAssignment]
    ) -> LectureAccessSettingsRead:
        assignments: list[LectureAssignmentRead] = []
        for row in rows:
            student_name = None
            section_name = None
            if row.student_user_id is not None:
                student = await self._users.get_by_id(row.student_user_id)
                student_name = student.display_name if student is not None else None
            if row.section_id is not None:
                section = await self._sections.get_by_id(row.section_id)
                section_name = section.name if section is not None else None
            assignments.append(
                LectureAssignmentRead(
                    id=row.id,
                    scope=AssignmentScopeSchema(row.scope.value),
                    student_user_id=row.student_user_id,
                    student_name=student_name,
                    section_id=row.section_id,
                    section_name=section_name,
                    created_at=row.created_at,
                )
            )
        return LectureAccessSettingsRead(
            lecture_id=lecture_id,
            is_restricted=len(assignments) > 0,
            assignments=assignments,
        )

    async def _require_lecture_for_access_management(
        self, claims: dict[str, object], lecture_id: str
    ) -> tuple[User, SchoolLecture, bool]:
        """Resolve (actor, lecture, is_elevated) for viewing/setting access settings.

        A Teacher must own the lecture. Coordinator/School Admin see any lecture
        in their own school, per §6.19 role inheritance ("X or higher within
        scope") plus the spec's explicit "School Admin can override restrictions
        (audit-logged)". District Admin/Platform Admin are allowed unconditionally
        here — proper district-level scoping is a known stub elsewhere in this
        codebase (see core/dependencies.require_scope's own docstring) and out of
        scope to build for this ticket. `is_elevated` is True whenever the actor
        is not the lecture's own teacher, so the caller can audit-log the action.
        """
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")

        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")

        if user.role == UserRole.TEACHER:
            if lecture.school_id != user.school_id or lecture.teacher_user_id != user.id:
                raise NotFoundError("Lecture not found")
            return user, lecture, False

        if user.role in (
            UserRole.COORDINATOR,
            UserRole.SCHOOL_ADMIN,
            UserRole.DISTRICT_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ):
            if user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
                if lecture.school_id != user.school_id:
                    raise NotFoundError("Lecture not found")
            return user, lecture, True

        raise PermissionDeniedError("Teacher, Coordinator, or Admin role required")

    async def get_lecture_access_settings(
        self, claims: dict[str, object], lecture_id: str
    ) -> LectureAccessSettingsRead:
        """Current access-restriction state for the lecture detail view (T-123, #21)."""
        _actor, lecture, _elevated = await self._require_lecture_for_access_management(
            claims, lecture_id
        )
        rows = await self._assignments.list_by_lecture(lecture.id)
        return await self._read_access_settings(lecture.id, rows)

    async def set_lecture_access_settings(
        self, claims: dict[str, object], lecture_id: str, payload: LectureAccessSettingsUpdate
    ) -> LectureAccessSettingsRead:
        """Replace-all restriction update. An empty list clears back to unrestricted.

        Each row is validated defensively even though the teacher UI only offers
        their own roster: a student/section not enrolled in the lecture's grade
        can never be assigned, mirroring acceptance item 3 (out-of-scope
        students can't gain access, including via a malformed/forged request).
        A Coordinator/Admin override is audit-logged per the spec's explicit
        "School Admin can override restrictions (audit-logged)" rule.
        """
        actor, lecture, elevated = await self._require_lecture_for_access_management(
            claims, lecture_id
        )
        if lecture.grade_subject_offering_id is None:
            raise ValidationError("Lecture has no Grade-Subject offering to restrict access within")
        offering = await self._offerings.get_by_id(lecture.grade_subject_offering_id)
        if offering is None:
            raise NotFoundError("Grade-Subject offering not found")

        rows: list[SchoolLectureAssignment] = []
        seen_students: set[str] = set()
        seen_sections: set[str] = set()
        for item in payload.assignments:
            if item.scope == AssignmentScopeSchema.STUDENT:
                if not item.student_user_id or item.section_id:
                    raise ValidationError(
                        "A student-scoped assignment needs student_user_id and no section_id"
                    )
                if item.student_user_id in seen_students:
                    raise ValidationError(f"Duplicate student assignment: {item.student_user_id}")
                enrollment = await self._enrollments.get_active_by_student_session(
                    item.student_user_id, offering.academic_session
                )
                if enrollment is None or enrollment.grade_id != offering.grade_id:
                    raise ValidationError(
                        f"Student {item.student_user_id} is not enrolled in this lecture's grade"
                    )
                seen_students.add(item.student_user_id)
                rows.append(
                    SchoolLectureAssignment(
                        lecture_id=lecture.id,
                        scope=AssignmentScopeModel.STUDENT,
                        student_user_id=item.student_user_id,
                        created_by_user_id=actor.id,
                    )
                )
            else:
                if not item.section_id or item.student_user_id:
                    raise ValidationError(
                        "A section-scoped assignment needs section_id and no student_user_id"
                    )
                if item.section_id in seen_sections:
                    raise ValidationError(f"Duplicate section assignment: {item.section_id}")
                section = await self._sections.get_by_id(item.section_id)
                if section is None or section.grade_id != offering.grade_id:
                    raise NotFoundError(
                        f"Section {item.section_id} not found in this lecture's grade"
                    )
                seen_sections.add(item.section_id)
                rows.append(
                    SchoolLectureAssignment(
                        lecture_id=lecture.id,
                        scope=AssignmentScopeModel.SECTION,
                        section_id=item.section_id,
                        created_by_user_id=actor.id,
                    )
                )

        saved = await self._assignments.replace_for_lecture(lecture.id, rows)
        logger.info(
            "lecture_access_settings_updated",
            lecture_id=lecture.id,
            actor_user_id=actor.id,
            elevated=elevated,
            assignment_count=len(saved),
        )
        await audit(
            session=self._session,
            action=LECTURE_ACCESS_OVERRIDDEN if elevated else LECTURE_ACCESS_CHANGED,
            actor_id=actor.id,
            actor_role=actor.role.value,
            target_type="lecture",
            target_id=lecture.id,
            school_id=lecture.school_id,
            metadata={"assignment_count": len(saved)},
        )
        return await self._read_access_settings(lecture.id, saved)

    async def get_lecture_roster(
        self, claims: dict[str, object], lecture_id: str
    ) -> LectureRosterRead:
        """The lecture's grade roster, to populate the access-restriction picker."""
        _actor, lecture, _elevated = await self._require_lecture_for_access_management(
            claims, lecture_id
        )
        if lecture.grade_subject_offering_id is None:
            return LectureRosterRead(sections=[], students=[])
        offering = await self._offerings.get_by_id(lecture.grade_subject_offering_id)
        if offering is None:
            return LectureRosterRead(sections=[], students=[])

        sections = await self._sections.list_visible_by_grade(offering.grade_id)
        enrollments = await self._enrollments.list_active_for_grade(
            offering.grade_id, offering.academic_session
        )
        students: list[RosterStudentRead] = []
        for enrollment in enrollments:
            user = await self._users.get_by_id(enrollment.student_user_id)
            if user is None:
                continue
            students.append(
                RosterStudentRead(
                    id=user.id,
                    display_name=user.display_name,
                    section_id=enrollment.section_id,
                )
            )
        return LectureRosterRead(
            sections=[RosterSectionRead(id=s.id, name=s.name) for s in sections],
            students=students,
        )

    async def student_can_access_lecture(self, student: User, lecture: SchoolLecture) -> bool:
        """Core server-side enforcement (T-123, #21).

        Default (no lecture_assignments rows): visible to every student actively
        enrolled in the lecture's Grade-Subject offering's grade. With rows: only
        students matched directly by student_user_id or via their section. Not
        wired to a student-facing endpoint yet (M-12 owns the viewer) — this is
        the function that viewer will gate reads through.
        """
        if lecture.grade_subject_offering_id is None:
            return False
        offering = await self._offerings.get_by_id(lecture.grade_subject_offering_id)
        if offering is None:
            return False
        enrollment = await self._enrollments.get_active_by_student_session(
            student.id, offering.academic_session
        )
        if enrollment is None or enrollment.grade_id != offering.grade_id:
            return False

        assignments = await self._assignments.list_by_lecture(lecture.id)
        if not assignments:
            return True

        for row in assignments:
            if row.scope == AssignmentScopeModel.STUDENT and row.student_user_id == student.id:
                return True
            if (
                row.scope == AssignmentScopeModel.SECTION
                and row.section_id == enrollment.section_id
            ):
                return True
        return False
