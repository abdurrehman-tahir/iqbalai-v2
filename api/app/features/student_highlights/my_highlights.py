"""My Highlights + paired flashcards — T-188 (flow-6 §3.6 / §4 / §5.5, #58).

Access matrix (flow-6 §4, ARCH §6.19, enforced here — never only in the UI):
- Student: own highlights + flashcards; may edit a card's back and delete a
  highlight (soft-delete cascades to the paired card, §5.5).
- Parent: read-only, approved link only, and only while the student shares
  study activity (#72 — INVIOLATE, no role overrides it).
- Coordinator / School Admin (own school), District Admin (own district),
  Platform Admin: anonymous per-lecture aggregates only — no text, no ids.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.lectures.models import SchoolLecture
from app.features.lectures.repository import LectureRepository
from app.features.parent_child_links.service import ParentChildLinkService
from app.features.schools.models import School
from app.features.student_highlights.flashcards import flashcard_dedupe_hash
from app.features.student_highlights.models import (
    SchoolStudentFlashcard,
    SchoolStudentHighlight,
)
from app.features.student_highlights.repository import (
    StudentFlashcardRepository,
    StudentHighlightRepository,
)
from app.features.student_highlights.schemas import (
    ConceptCountRead,
    HighlightLectureRefRead,
    LectureHighlightAggregateRead,
    MyHighlightRead,
    PairedFlashcardRead,
)
from app.features.student_privacy.service import student_allows_teacher_share
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

MAX_PAGE_SIZE = 100
_AGGREGATE_ROLES = (
    UserRole.COORDINATOR,
    UserRole.SCHOOL_ADMIN,
    UserRole.DISTRICT_ADMIN,
    UserRole.PLATFORM_ADMIN,
)


def flashcard_to_read(card: SchoolStudentFlashcard) -> PairedFlashcardRead:
    return PairedFlashcardRead(
        id=card.id,
        front_text=card.front_text,
        back_text=card.back_text,
        back_is_placeholder=card.back_text == "",
        status=card.status.value,
        concept_tag=card.concept_tag,
        created_at=card.created_at,
    )


def _row_to_read(
    highlight: SchoolStudentHighlight,
    lecture: SchoolLecture,
    card: SchoolStudentFlashcard | None,
) -> MyHighlightRead:
    return MyHighlightRead(
        id=highlight.id,
        highlighted_text=highlight.highlighted_text,
        concept_tag=highlight.concept_tag,
        created_at=highlight.created_at,
        lecture=HighlightLectureRefRead(id=lecture.id, title=lecture.title, topic=lecture.topic),
        paragraph_ordinal=highlight.paragraph_ordinal,
        question_id=highlight.question_id,
        flashcard=flashcard_to_read(card) if card is not None else None,
    )


class MyHighlightsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._highlights = StudentHighlightRepository(session)
        self._flashcards = StudentFlashcardRepository(session)

    async def _require_user(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        return user

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._require_user(claims)
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def _feed(
        self, student_user_id: str, *, page: int, page_size: int
    ) -> tuple[list[MyHighlightRead], int]:
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        page = max(1, page)
        rows = await self._highlights.list_for_student_with_lectures(
            student_user_id=student_user_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        total = await self._highlights.count_for_student(student_user_id=student_user_id)
        hashes = {
            h.id: flashcard_dedupe_hash(highlight_text=h.highlighted_text, lecture_id=h.lecture_id)
            for h, _ in rows
        }
        cards = await self._flashcards.live_by_hashes(
            student_user_id=student_user_id, dedupe_hashes=sorted(set(hashes.values()))
        )
        return [_row_to_read(h, lec, cards.get(hashes[h.id])) for h, lec in rows], total

    # --- student ---------------------------------------------------------------

    async def list_mine(
        self, claims: dict[str, object], *, page: int, page_size: int
    ) -> tuple[list[MyHighlightRead], int]:
        student = await self._require_student(claims)
        return await self._feed(student.id, page=page, page_size=page_size)

    async def update_flashcard_back(
        self, claims: dict[str, object], *, flashcard_id: str, back_text: str
    ) -> PairedFlashcardRead:
        student = await self._require_student(claims)
        card = await self._flashcards.get_owned(
            flashcard_id=flashcard_id, student_user_id=student.id
        )
        if card is None:
            raise NotFoundError("Flashcard not found")
        card.back_text = back_text.strip()
        await self._session.flush()
        await self._session.commit()
        return flashcard_to_read(card)

    async def delete_highlight(self, claims: dict[str, object], *, highlight_id: str) -> None:
        """Soft-delete the highlight and its paired card (§5.5 "cascade").

        The card is shared by repeat highlights of the same text; it is removed
        only when no other live highlight of this student still pairs with it.
        """
        student = await self._require_student(claims)
        highlight = await self._highlights.get_owned(
            highlight_id=highlight_id, student_user_id=student.id
        )
        if highlight is None:
            raise NotFoundError("Highlight not found")
        now = datetime.now(timezone.utc)
        highlight.deleted_at = now

        dedupe = flashcard_dedupe_hash(
            highlight_text=highlight.highlighted_text, lecture_id=highlight.lecture_id
        )
        siblings = await self._session.execute(
            select(SchoolStudentHighlight).where(
                SchoolStudentHighlight.student_user_id == student.id,
                SchoolStudentHighlight.lecture_id == highlight.lecture_id,
                SchoolStudentHighlight.id != highlight.id,
                SchoolStudentHighlight.deleted_at.is_(None),
            )
        )
        still_paired = any(
            flashcard_dedupe_hash(highlight_text=s.highlighted_text, lecture_id=s.lecture_id)
            == dedupe
            for s in siblings.scalars().all()
        )
        if not still_paired:
            cards = await self._flashcards.live_by_hashes(
                student_user_id=student.id, dedupe_hashes=[dedupe]
            )
            card = cards.get(dedupe)
            if card is not None:
                card.deleted_at = now
        await self._session.flush()
        await self._session.commit()

    # --- parent (read-only, #72) ----------------------------------------------

    async def list_for_parent(
        self,
        claims: dict[str, object],
        *,
        student_user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[MyHighlightRead], int]:
        access = await ParentChildLinkService(self._session).get_parent_student_access_state(
            student_user_id, claims
        )
        if not access.read_only_access:
            raise PermissionDeniedError("No approved parent-child link for this student")
        if not await student_allows_teacher_share(self._session, student_user_id):
            return [], 0  # #72 opt-out: nothing is observable, not even a count
        return await self._feed(student_user_id, page=page, page_size=page_size)

    # --- coordinator / admin aggregate ----------------------------------------

    async def lecture_aggregate(
        self, claims: dict[str, object], *, lecture_id: str
    ) -> LectureHighlightAggregateRead:
        user = await self._require_user(claims)
        if user.role not in _AGGREGATE_ROLES:
            raise PermissionDeniedError("Coordinator or Admin role required")
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None or lecture.deleted_at is not None:
            raise NotFoundError("Lecture not found")
        if user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
            if lecture.school_id is None or lecture.school_id != user.school_id:
                raise NotFoundError("Lecture not found")
        elif user.role == UserRole.DISTRICT_ADMIN:
            school = (
                await self._session.get(School, lecture.school_id) if lecture.school_id else None
            )
            if school is None or school.district_id != user.district_id:
                raise NotFoundError("Lecture not found")

        population = await self._sharing_students_for_lecture(lecture_id)
        agg = await self._highlights.aggregate_for_lecture(
            lecture_id=lecture_id, student_ids=population
        )
        return LectureHighlightAggregateRead(
            lecture_id=agg.lecture_id,
            highlight_count=agg.highlight_count,
            student_count=agg.student_count,
            flashcard_count=agg.flashcard_count,
            top_concepts=[ConceptCountRead(concept_tag=c, count=n) for c, n in agg.top_concepts],
        )

    async def _sharing_students_for_lecture(self, lecture_id: str) -> list[str]:
        """Students with highlights on the lecture who still share activity (#72)."""
        result = await self._session.execute(
            select(SchoolStudentHighlight.student_user_id)
            .where(
                SchoolStudentHighlight.lecture_id == lecture_id,
                SchoolStudentHighlight.deleted_at.is_(None),
            )
            .distinct()
        )
        ids = [str(r) for r in result.scalars().all()]
        return [sid for sid in ids if await student_allows_teacher_share(self._session, sid)]


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / max(1, page_size)))
