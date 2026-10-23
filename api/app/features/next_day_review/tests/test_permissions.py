"""T-207 — Flow 7 §4 permissions matrix, derived from the ``UserRole`` union.

Every role must appear in ``EXPECTED`` (the test fails when a role is added
without a decision), and cases are generated from the enum — never a
hand-picked subset (CLAUDE.md rule 14). Plus the DLQ alert (§7).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.next_day_review import assembly
from app.features.next_day_review.assembly import alert_classification_failures
from app.features.next_day_review.service import NextDayReviewService
from app.features.next_day_review.tests.conftest import World, make_user
from app.features.schools.models import School
from app.features.users.models import UserRole

# role -> (can view, sees student names, can act on the card); None = denied outright.
EXPECTED: dict[UserRole, tuple[bool, bool, bool] | None] = {
    UserRole.TEACHER: (True, True, True),  # the owning teacher
    UserRole.COORDINATOR: (True, False, False),  # view-only, aggregate
    UserRole.SCHOOL_ADMIN: (True, False, True),  # aggregate, override (audited)
    UserRole.DISTRICT_ADMIN: (True, False, True),  # inherits in district scope
    UserRole.PLATFORM_ADMIN: (True, False, True),  # inherits everywhere
    UserRole.STUDENT: None,
    UserRole.PARENT: None,
}


def test_matrix_covers_every_role() -> None:
    assert set(EXPECTED) == set(UserRole)


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.next_day_review.service._offering_label", AsyncMock(return_value="G9")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(UserRole), ids=lambda r: r.value)
async def test_role_view_names_and_actions(world: World, as_user: Any, role: UserRole) -> None:
    user = world.teacher if role == UserRole.TEACHER else make_user(role, f"{role.value}-1")
    if role == UserRole.DISTRICT_ADMIN:
        user.district_id = "district-1"
        world.objects[(School, "school-1")] = School(id="school-1", district_id="district-1")
    claims = as_user(user)
    service = NextDayReviewService(world.session())
    service._student_names = AsyncMock(return_value={"stu-0": "Ali"})  # type: ignore[method-assign]

    expected = EXPECTED[role]
    if expected is None:
        with pytest.raises(PermissionDeniedError):
            await service.get_review(claims, "rev-1")
        return

    can_view, sees_names, can_act = expected
    detail = await service.get_review(claims, "rev-1")
    assert can_view
    assert (detail.critical[0].questions[0].student_name is not None) is sees_names
    assert detail.can_act is can_act
    # Teacher-only actions (reflect / reply / skip) never extend to admins.
    assert detail.is_owner is (role == UserRole.TEACHER)


@pytest.mark.asyncio
async def test_district_admin_outside_district_gets_404(world: World, as_user: Any) -> None:
    admin = make_user(UserRole.DISTRICT_ADMIN, "da-9")
    admin.district_id = "district-9"
    world.objects[(School, "school-1")] = School(id="school-1", district_id="district-1")
    with pytest.raises(NotFoundError):
        await NextDayReviewService(world.session()).get_review(as_user(admin), "rev-1")


@pytest.mark.asyncio
async def test_dlq_alert_goes_to_platform_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr(assembly, "notify_all_platform_admins", notify)
    session = MagicMock(commit=AsyncMock())
    await alert_classification_failures(
        session, school_id="school-1", review_date=date(2026, 10, 22), count=2
    )
    assert notify.await_args is not None
    assert notify.await_args.kwargs["template_key"] == "system.review_classification_failures"
    assert notify.await_args.kwargs["params"] == {"count": "2", "date": "2026-10-22"}


@pytest.mark.asyncio
async def test_no_dlq_alert_when_nothing_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr(assembly, "notify_all_platform_admins", notify)
    await alert_classification_failures(
        MagicMock(), school_id="school-1", review_date=date(2026, 10, 22), count=0
    )
    notify.assert_not_awaited()
