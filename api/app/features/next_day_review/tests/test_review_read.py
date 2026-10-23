"""T-201 — review card read model + §6.19 visibility (teacher-only names)."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.lectures.models import LectureStatus
from app.features.next_day_review.service import NextDayReviewService, plain_preview
from app.features.next_day_review.tests.conftest import World, make_user
from app.features.users.models import UserRole


@pytest.fixture(autouse=True)
def _label(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _offering_label(_session: Any, _gso: str) -> str:
        return "Grade 9 Physics"

    monkeypatch.setattr("app.features.next_day_review.service._offering_label", _offering_label)


def test_plain_preview_strips_markup_and_truncates() -> None:
    text = plain_preview("<h1># Title</h1><p>**Bold** " + "word " * 100 + "</p>")
    assert "<" not in text and "#" not in text and "*" not in text
    assert len(text) <= 201
    assert text.endswith("…")


@pytest.mark.asyncio
async def test_owner_sees_card_with_names_preview_and_columns(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    service = NextDayReviewService(world.session())
    service._student_names = _names  # type: ignore[method-assign]

    detail = await service.get_review(claims, "rev-1")

    assert detail.is_owner is True and detail.can_act is True
    assert detail.offering_label == "Grade 9 Physics"
    assert [c.cluster_ref for c in detail.critical] == ["a"]
    assert [c.cluster_ref for c in detail.high_frequency] == ["b"]
    q = detail.critical[0].questions[0]
    assert q.student_user_id == "stu-0"
    assert q.student_name == "Ali"
    assert detail.mini_preview is not None and len(detail.mini_preview) <= 201
    assert detail.mini_published is False
    assert detail.pending_action is True


async def _names(ids: set[str]) -> dict[str, str]:
    return {"stu-0": "Ali", "stu-1": "Sara", "stu-2": "Bilal"}


@pytest.mark.asyncio
async def test_coordinator_gets_aggregate_only_and_cannot_act(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.COORDINATOR, "coord-1"))
    detail = await NextDayReviewService(world.session()).get_review(claims, "rev-1")
    assert detail.is_owner is False
    assert detail.can_act is False
    q = detail.critical[0].questions[0]
    assert q.question_text  # wording visible
    assert q.student_user_id is None and q.student_name is None
    assert detail.replies == []


@pytest.mark.asyncio
async def test_school_admin_can_override_but_sees_no_names(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.SCHOOL_ADMIN, "admin-1"))
    detail = await NextDayReviewService(world.session()).get_review(claims, "rev-1")
    assert detail.can_act is True
    assert detail.critical[0].questions[0].student_name is None


@pytest.mark.asyncio
async def test_other_teacher_gets_404(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.TEACHER, "teacher-2"))
    with pytest.raises(NotFoundError):
        await NextDayReviewService(world.session()).get_review(claims, "rev-1")


@pytest.mark.asyncio
async def test_other_school_coordinator_gets_404(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.COORDINATOR, "coord-9", school_id="school-9"))
    with pytest.raises(NotFoundError):
        await NextDayReviewService(world.session()).get_review(claims, "rev-1")


@pytest.mark.asyncio
async def test_student_is_denied(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.STUDENT, "stu-0"))
    with pytest.raises(PermissionDeniedError):
        await NextDayReviewService(world.session()).get_review(claims, "rev-1")


@pytest.mark.asyncio
async def test_archived_lecture_review_is_read_only(world: World, as_user: Any) -> None:
    world.lecture.status = LectureStatus.ARCHIVED
    claims = as_user(world.teacher)
    service = NextDayReviewService(world.session())
    service._student_names = _names  # type: ignore[method-assign]
    detail = await service.get_review(claims, "rev-1")
    assert detail.read_only is True
    assert detail.can_act is False


@pytest.mark.asyncio
async def test_list_returns_summaries_with_column_counts(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    world.execute_rows = [(world.review, world.lecture)]
    rows = await NextDayReviewService(world.session()).list_reviews(claims, lecture_id="lec-1")
    assert len(rows) == 1
    assert rows[0].critical_count == 1
    assert rows[0].high_frequency_count == 1
    assert rows[0].lecture_title == "Newton's Laws"
