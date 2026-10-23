"""T-204 — targeted mini-lecture distribution + mini guards (no auto-quiz, no cross-grade)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import PreconditionFailedError, ValidationError
from app.features.audit.actions import REVIEW_MINI_PUBLISHED, REVIEW_OVERRIDE_ACTION
from app.features.lectures.models import LectureStatus, LectureType
from app.features.lectures.repository import LectureAssignmentRepository
from app.features.lectures.schemas import LectureLinkCreate
from app.features.lectures.service import LectureWizardService
from app.features.next_day_review import distribution
from app.features.next_day_review.distribution import (
    MINI_LECTURE_ASSIGNED_EVENT,
    assign_recipients,
    triggering_students,
)
from app.features.next_day_review.models import LectureReviewStatus
from app.features.next_day_review.schemas import ReviewClusterSnapshot
from app.features.next_day_review.service import ACTION_PUBLISH_MINI, NextDayReviewService
from app.features.next_day_review.tests.conftest import World, make_snapshot, make_user
from app.features.quizzes.generation import enqueue_quiz_generation_for_lecture
from app.features.users.models import UserRole

# Cluster "a" carries mini-1 (stu-0..2); "b" has no mini (stu-0..4).
SNAPS = [
    ReviewClusterSnapshot.model_validate(make_snapshot("a")),
    ReviewClusterSnapshot.model_validate(make_snapshot("b", "high_frequency", students=5)),
]


def test_recipients_are_only_the_triggering_students() -> None:
    students = triggering_students(SNAPS, mini_lecture_id="mini-1", skipped=set())
    assert students == {"stu-0", "stu-1", "stu-2"}


def test_skipped_cluster_falls_back_to_remaining_clusters() -> None:
    students = triggering_students(SNAPS, mini_lecture_id="mini-1", skipped={"a"})
    assert students == {"stu-0", "stu-1", "stu-2", "stu-3", "stu-4"}


@pytest.mark.asyncio
async def test_unenrolled_students_are_dropped(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        distribution, "enrolled_recipients", AsyncMock(return_value={"stu-0", "stu-2"})
    )
    replace = AsyncMock()
    monkeypatch.setattr(LectureAssignmentRepository, "replace_for_lecture", replace)
    recipients = await assign_recipients(
        world.session(),
        mini=world.mini,
        gso_id="gso-1",
        candidates={"stu-0", "stu-1", "stu-2"},
        actor_user_id="teacher-1",
    )
    assert recipients == ["stu-0", "stu-2"]
    rows = replace.await_args.args[1] if replace.await_args else []
    assert [r.student_user_id for r in rows] == ["stu-0", "stu-2"]
    assert {r.lecture_id for r in rows} == {"mini-1"}


@pytest.mark.asyncio
async def test_all_unenrolled_is_precondition_failed(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(distribution, "enrolled_recipients", AsyncMock(return_value=set()))
    with pytest.raises(PreconditionFailedError):
        await assign_recipients(
            world.session(),
            mini=world.mini,
            gso_id="gso-1",
            candidates={"stu-0"},
            actor_user_id="teacher-1",
        )


# --- service publish -----------------------------------------------------------------


@pytest.fixture
def publish_mocks(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    mocks = {
        "assign": AsyncMock(return_value=["stu-0", "stu-1"]),
        "notify": AsyncMock(return_value=2),
        "event": AsyncMock(),
        "audit": AsyncMock(),
    }
    base = "app.features.next_day_review.service."
    monkeypatch.setattr(base + "assign_recipients", mocks["assign"])
    monkeypatch.setattr(base + "notify_recipients", mocks["notify"])
    monkeypatch.setattr(base + "publish_lecture_event", mocks["event"])
    monkeypatch.setattr(base + "audit", mocks["audit"])
    monkeypatch.setattr(base + "skipped_refs", AsyncMock(return_value=set()))
    monkeypatch.setattr(base + "_offering_label", AsyncMock(return_value="G9"))
    return mocks


def _service(world: World) -> NextDayReviewService:
    service = NextDayReviewService(world.session())
    service._student_names = AsyncMock(return_value={})  # type: ignore[method-assign]
    return service


@pytest.mark.asyncio
async def test_teacher_publishes_mini_to_triggering_students(
    world: World, as_user: Any, publish_mocks: dict[str, AsyncMock]
) -> None:
    claims = as_user(world.teacher)
    await _service(world).publish_mini(claims, "rev-1")

    assign = publish_mocks["assign"].await_args
    assert assign is not None
    assert assign.kwargs["candidates"] == {"stu-0", "stu-1", "stu-2"}
    assert world.mini.status == LectureStatus.PUBLISHED
    assert ACTION_PUBLISH_MINI in world.review.acted_actions
    assert world.review.status == LectureReviewStatus.COMPLETED
    event = publish_mocks["event"].await_args
    assert event is not None and event.kwargs["event_type"] == MINI_LECTURE_ASSIGNED_EVENT
    assert event.kwargs["payload"]["recipient_user_ids"] == ["stu-0", "stu-1"]
    audit = publish_mocks["audit"].await_args
    assert audit is not None and audit.kwargs["action"] == REVIEW_MINI_PUBLISHED
    publish_mocks["notify"].assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_publish_is_an_audited_override(
    world: World, as_user: Any, publish_mocks: dict[str, AsyncMock]
) -> None:
    claims = as_user(make_user(UserRole.SCHOOL_ADMIN, "admin-1"))
    await _service(world).publish_mini(claims, "rev-1")
    actions = [c.kwargs["action"] for c in publish_mocks["audit"].await_args_list]
    assert actions == [REVIEW_OVERRIDE_ACTION, REVIEW_MINI_PUBLISHED]


@pytest.mark.asyncio
async def test_mini_still_generating_cannot_publish(
    world: World, as_user: Any, publish_mocks: dict[str, AsyncMock]
) -> None:
    world.mini.status = LectureStatus.GENERATING
    claims = as_user(world.teacher)
    with pytest.raises(ValidationError):
        await _service(world).publish_mini(claims, "rev-1")
    publish_mocks["assign"].assert_not_awaited()


@pytest.mark.asyncio
async def test_review_without_mini_cannot_publish(
    world: World, as_user: Any, publish_mocks: dict[str, AsyncMock]
) -> None:
    world.review.mini_lecture_id = None
    claims = as_user(world.teacher)
    with pytest.raises(ValidationError):
        await _service(world).publish_mini(claims, "rev-1")


# --- guards elsewhere ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_auto_quiz_for_mini_lectures(world: World) -> None:
    session = MagicMock()
    assert await enqueue_quiz_generation_for_lecture(session, lecture=world.mini) == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_cross_grade_link_blocked_for_mini(world: World) -> None:
    service = LectureWizardService(MagicMock())
    service._require_school_teacher = AsyncMock(return_value=world.teacher)  # type: ignore[method-assign]
    service._require_owned_lecture = AsyncMock(return_value=world.mini)  # type: ignore[method-assign]
    with pytest.raises(ValidationError):
        await service.link_lecture(
            {"sub": "ak-teacher-1"},
            "mini-1",
            LectureLinkCreate(target_grade_subject_offering_id="gso-2"),
        )


@pytest.mark.asyncio
async def test_wizard_publish_refuses_mini(world: World) -> None:
    assert world.mini.lecture_type == LectureType.MINI
    service = LectureWizardService(MagicMock())
    service._require_lecture_for_access_management = AsyncMock(  # type: ignore[method-assign]
        return_value=(world.teacher, world.mini, False)
    )
    with pytest.raises(ValidationError):
        await service.publish_lecture({"sub": "ak-teacher-1"}, "mini-1")
