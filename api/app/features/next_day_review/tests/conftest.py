"""Shared fakes for the M-16 review service / API tests (no DB, no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureVersion,
)
from app.features.next_day_review.models import LectureReview
from app.features.users.models import User, UserRole

REVIEW_DATE = date(2026, 10, 22)


def make_user(role: UserRole, uid: str, *, school_id: str = "school-1") -> User:
    return User(
        id=uid,
        authentik_id=f"ak-{uid}",
        email=f"{uid}@example.test",
        display_name=f"User {uid}",
        role=role,
        school_id=school_id,
    )


def make_snapshot(ref: str, column: str = "critical", students: int = 3) -> dict[str, Any]:
    return {
        "cluster_ref": ref,
        "lecture_id": "lec-1",
        "column": column,
        "question_count": students,
        "unique_student_count": students,
        "criticality": 8 if column == "critical" else 3,
        "freq_score": 1.0,
        "representative_question": f"Why {ref}?",
        "mini_lecture_id": "mini-1" if ref == "a" else None,
        "questions": [
            {
                "question_id": f"{ref}-q{i}",
                "student_user_id": f"stu-{i}",
                "question_text": f"Why {ref}? ({i})",
                "paragraph_id": "p1",
                "source_chunk_id": "c1",
                "occurred_at": "2026-10-22T10:00:00+00:00",
            }
            for i in range(students)
        ],
    }


class FakeResult:
    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self) -> list[Any]:
        return self._rows

    def first(self) -> Any:
        return ("Grade 9", "Physics")

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalars(self) -> Any:
        rows = self._rows
        return MagicMock(all=lambda: rows)


class World:
    """In-memory objects a fake AsyncSession serves by (model, pk)."""

    def __init__(self) -> None:
        self.teacher = make_user(UserRole.TEACHER, "teacher-1")
        self.lecture = SchoolLecture(
            id="lec-1",
            school_id="school-1",
            teacher_user_id="teacher-1",
            title="Newton's Laws",
            topic="Newton's third law",
            grade_subject_offering_id="gso-1",
            status=LectureStatus.PUBLISHED,
        )
        self.mini = SchoolLecture(
            id="mini-1",
            school_id="school-1",
            teacher_user_id="teacher-1",
            title="Mini: action-reaction",
            topic="Mini: action-reaction",
            grade_subject_offering_id="gso-1",
            lecture_type=LectureType.MINI,
            parent_lecture_id="lec-1",
            status=LectureStatus.READY_FOR_EDIT,
            current_version_id="mver-1",
        )
        self.mini_version = SchoolLectureVersion(
            id="mver-1", lecture_id="mini-1", version=1, body="<p>" + "Force pairs. " * 30 + "</p>"
        )
        self.review = LectureReview(
            id="rev-1",
            lecture_id="lec-1",
            gso_id="gso-1",
            review_date=REVIEW_DATE,
            ai_summary="Students mixed up forces.",
            reflective_prompt="Would a worked example help?",
            clusters_jsonb=[make_snapshot("a"), make_snapshot("b", "high_frequency")],
            mini_lecture_id="mini-1",
            generated_at=datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc),
        )
        self.review.created_at = datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc)
        self.review.updated_at = self.review.created_at
        self.objects: dict[tuple[type[Any], str], Any] = {
            (SchoolLecture, "lec-1"): self.lecture,
            (SchoolLecture, "mini-1"): self.mini,
            (SchoolLectureVersion, "mver-1"): self.mini_version,
            (LectureReview, "rev-1"): self.review,
        }
        self.added: list[Any] = []
        self.execute_rows: list[Any] = []

    def session(self) -> MagicMock:
        session = MagicMock()

        async def _get(model: type[Any], pk: str) -> Any:
            return self.objects.get((model, pk))

        async def _execute(*_a: Any, **_k: Any) -> FakeResult:
            return FakeResult(rows=list(self.execute_rows))

        session.get = AsyncMock(side_effect=_get)
        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock(side_effect=self.added.append)
        return session


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def as_user(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Make ``UserRepository.get_by_authentik_id`` return the given user."""

    def _set(user: User) -> dict[str, object]:
        monkeypatch.setattr(
            "app.features.next_day_review.service.UserRepository.get_by_authentik_id",
            AsyncMock(return_value=user),
        )
        return {"sub": user.authentik_id, "role": user.role.value, "school_id": user.school_id}

    return _set
