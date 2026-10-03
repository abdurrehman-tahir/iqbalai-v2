"""Student highlight service — T-185 (Flow 6 §3.6 / §5.5, #58).

Write path: ``persist_for_question`` is called from the ask-question path
(HIGHLIGHT_PERSISTED precedes the AI answer in the §3.6 lifecycle); it only
stages the row — the caller owns the commit.

Read path: ``list_for_lecture`` re-verifies every anchor against the
lecture's *current* version and returns ``mark=None`` for spans that no
longer map (silent drop, §5.5).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.lectures.models import SchoolLecture, SchoolLectureParagraph
from app.features.lectures.repository import LectureParagraphRepository, LectureRepository
from app.features.lectures.service import LectureService
from app.features.session_difficulty.subtopic import resolve_sub_topic_id
from app.features.student_highlights.anchoring import locate_anchor, resolve_mark
from app.features.student_highlights.models import HighlightTenantType, SchoolStudentHighlight
from app.features.student_highlights.repository import StudentHighlightRepository
from app.features.student_highlights.schemas import HighlightMarkRead, StudentHighlightRead
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository


def highlight_to_read(
    row: SchoolStudentHighlight, mark: HighlightMarkRead | None
) -> StudentHighlightRead:
    return StudentHighlightRead(
        id=row.id,
        lecture_id=row.lecture_id,
        lecture_version_id=row.lecture_version_id,
        paragraph_ordinal=row.paragraph_ordinal,
        text_range_offset=row.text_range_offset,
        text_range_length=row.text_range_length,
        highlighted_text=row.highlighted_text,
        question_id=row.question_id,
        concept_tag=row.concept_tag,
        tenant_type=row.tenant_type.value,
        created_at=row.created_at,
        mark=mark,
    )


def resolve_marks(
    rows: list[SchoolStudentHighlight], paragraphs: list[SchoolLectureParagraph]
) -> list[StudentHighlightRead]:
    current = [(p.ordinal, p.id, p.text) for p in paragraphs]
    out: list[StudentHighlightRead] = []
    for row in rows:
        resolved = resolve_mark(
            paragraph_ordinal=row.paragraph_ordinal,
            offset=row.text_range_offset,
            length=row.text_range_length,
            highlighted_text=row.highlighted_text,
            current_paragraphs=current,
        )
        mark = (
            HighlightMarkRead(
                paragraph_id=resolved.paragraph_id,
                offset=resolved.offset,
                length=resolved.length,
            )
            if resolved is not None
            else None
        )
        out.append(highlight_to_read(row, mark))
    return out


class StudentHighlightService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._paragraphs = LectureParagraphRepository(session)
        self._lecture_svc = LectureService(session)
        self._highlights = StudentHighlightRepository(session)

    async def persist_for_question(
        self,
        *,
        student_user_id: str,
        lecture: SchoolLecture,
        question_id: str,
        tenant_type: str,
        paragraph: SchoolLectureParagraph | None,
        highlighted_text: str | None,
        offset_hint: int | None,
        source_chunk_id: str | None,
    ) -> SchoolStudentHighlight | None:
        """Stage a highlight row for a highlight-triggered question.

        Returns ``None`` (nothing stored) when there is no highlight or the
        selection can't be anchored inside its paragraph — e.g. free-form
        questions, or a selection spanning paragraphs.
        """
        if not highlighted_text or paragraph is None:
            return None
        # flow-6 §5.10: a graduated student in the school read-only window can view
        # past lectures and highlights but cannot create new highlights (and so no
        # new flashcards either).
        profile = await self._session.get(StudentProfile, student_user_id)
        if profile is not None and profile.is_graduated and not profile.migrated_out:
            return None
        anchor = locate_anchor(paragraph.text, highlighted_text, offset_hint)
        if anchor is None:
            return None
        concept_tag = await resolve_sub_topic_id(
            self._session,
            source_chunk_id=source_chunk_id,
            lecture_id=lecture.id,
            paragraph_id=paragraph.id,
        )
        row = SchoolStudentHighlight(
            student_user_id=student_user_id,
            lecture_id=lecture.id,
            lecture_version_id=paragraph.lecture_version_id,
            paragraph_id=paragraph.id,
            paragraph_ordinal=paragraph.ordinal,
            text_range_offset=anchor.offset,
            text_range_length=anchor.length,
            highlighted_text=highlighted_text,
            question_id=question_id,
            concept_tag=concept_tag,
            tenant_type=HighlightTenantType(tenant_type),
        )
        return await self._highlights.create(row)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def list_for_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[StudentHighlightRead]:
        """The caller's own highlights on a lecture, with yellow-mark positions.

        Access goes through the same GSO/enrollment gate as the viewer, and rows
        are owner-scoped, so another student — or a student of another school —
        never sees them.
        """
        student = await self._require_student(claims)
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")

        rows = await self._highlights.list_for_student_lecture(
            student_user_id=student.id, lecture_id=lecture_id
        )
        paragraphs: list[SchoolLectureParagraph] = []
        if lecture.current_version_id is not None:
            paragraphs = await self._paragraphs.list_by_version(lecture.current_version_id)
        return resolve_marks(rows, paragraphs)
