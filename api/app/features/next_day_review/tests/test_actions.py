"""T-205 — review card actions: edit main, dismiss (recoverable), reopen, multi-action."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PermissionDeniedError, ValidationError
from app.features.audit.actions import REVIEW_DISMISSED, REVIEW_OVERRIDE_ACTION
from app.features.next_day_review.models import LectureReviewStatus
from app.features.next_day_review.service import (
    ACTION_DISMISS,
    ACTION_EDIT_MAIN,
    NextDayReviewService,
)
from app.features.next_day_review.tests.conftest import World, make_user
from app.features.users.models import UserRole


@pytest.fixture(autouse=True)
def audit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    monkeypatch.setattr(
        "app.features.next_day_review.service._offering_label", AsyncMock(return_value="G9")
    )
    mock = AsyncMock()
    monkeypatch.setattr("app.features.next_day_review.service.audit", mock)
    return mock


def _service(world: World) -> NextDayReviewService:
    service = NextDayReviewService(world.session())
    service._student_names = AsyncMock(return_value={})  # type: ignore[method-assign]
    return service


@pytest.mark.asyncio
async def test_edit_main_records_action(world: World, as_user: Any) -> None:
    detail = await _service(world).edit_main(as_user(world.teacher), "rev-1")
    assert ACTION_EDIT_MAIN in detail.acted_actions
    assert world.review.status == LectureReviewStatus.COMPLETED
    assert world.review.pending_action is False


@pytest.mark.asyncio
async def test_dismiss_is_recoverable(world: World, as_user: Any, audit: AsyncMock) -> None:
    claims = as_user(world.teacher)
    service = _service(world)
    await service.dismiss(claims, "rev-1")
    assert world.review.dismissed_at is not None
    assert world.review.status == LectureReviewStatus.DISMISSED
    assert audit.await_args is not None and audit.await_args.kwargs["action"] == REVIEW_DISMISSED

    detail = await service.reopen(claims, "rev-1")
    assert world.review.dismissed_at is None
    assert detail.status == LectureReviewStatus.PENDING
    assert detail.pending_action is True
    assert ACTION_DISMISS in detail.acted_actions  # history kept


@pytest.mark.asyncio
async def test_multiple_actions_accumulate(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    service = _service(world)
    await service.edit_main(claims, "rev-1")
    await service.edit_main(claims, "rev-1")
    await service.dismiss(claims, "rev-1")
    assert world.review.acted_actions == [ACTION_EDIT_MAIN, ACTION_DISMISS]


@pytest.mark.asyncio
async def test_reopen_requires_dismissed(world: World, as_user: Any) -> None:
    with pytest.raises(ValidationError):
        await _service(world).reopen(as_user(world.teacher), "rev-1")


@pytest.mark.asyncio
async def test_coordinator_cannot_dismiss(world: World, as_user: Any) -> None:
    with pytest.raises(PermissionDeniedError):
        await _service(world).dismiss(as_user(make_user(UserRole.COORDINATOR, "c-1")), "rev-1")


@pytest.mark.asyncio
async def test_admin_dismiss_is_audited_override(
    world: World, as_user: Any, audit: AsyncMock
) -> None:
    await _service(world).dismiss(as_user(make_user(UserRole.SCHOOL_ADMIN, "a-1")), "rev-1")
    actions = [c.kwargs["action"] for c in audit.await_args_list]
    assert actions == [REVIEW_OVERRIDE_ACTION, REVIEW_DISMISSED]


@pytest.mark.asyncio
async def test_first_action_stamps_acted_at_once(world: World, as_user: Any) -> None:
    """T-206: acted_at = first action — later actions must not move it ("days to act")."""
    claims = as_user(world.teacher)
    service = _service(world)
    await service.edit_main(claims, "rev-1")
    first = world.review.acted_at
    assert first is not None
    await service.dismiss(claims, "rev-1")
    assert world.review.acted_at == first
