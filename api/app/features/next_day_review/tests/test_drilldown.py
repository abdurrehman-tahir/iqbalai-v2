"""T-203 — drill-down replies, cluster skip and skip-aware mini regeneration."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.audit.actions import REVIEW_CLUSTER_SKIPPED, REVIEW_OVERRIDE_ACTION
from app.features.next_day_review import regeneration
from app.features.next_day_review.models import ReviewReply, SkippedCluster
from app.features.next_day_review.regeneration import (
    as_classified,
    pick_cluster,
    regenerate_review_mini,
)
from app.features.next_day_review.schemas import ReviewClusterSnapshot, ReviewReplyCreate
from app.features.next_day_review.service import (
    ACTION_REPLY,
    ACTION_SKIP,
    NextDayReviewService,
)
from app.features.next_day_review.tests.conftest import World, make_snapshot, make_user
from app.features.users.models import UserRole


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    monkeypatch.setattr(
        "app.features.next_day_review.service._offering_label", AsyncMock(return_value="G9")
    )
    audit = AsyncMock()
    monkeypatch.setattr("app.features.next_day_review.service.audit", audit)
    return audit


def _service(world: World) -> NextDayReviewService:
    service = NextDayReviewService(world.session())
    service._student_names = AsyncMock(return_value={})  # type: ignore[method-assign]
    return service


# --- pure helpers -------------------------------------------------------------------


def test_pick_cluster_prefers_critical_and_ignores_skipped() -> None:
    snaps = [
        ReviewClusterSnapshot.model_validate(make_snapshot("big", "high_frequency", students=9)),
        ReviewClusterSnapshot.model_validate(make_snapshot("crit", "critical", students=2)),
    ]
    picked = pick_cluster(snaps, set())
    assert picked is not None and picked.cluster_ref == "crit"
    picked = pick_cluster(snaps, {"crit"})
    assert picked is not None and picked.cluster_ref == "big"
    assert pick_cluster(snaps, {"crit", "big"}) is None


def test_as_classified_rebuilds_generator_input() -> None:
    snap = ReviewClusterSnapshot.model_validate(make_snapshot("a"))
    cluster = as_classified(snap, "gso-1")
    assert cluster.qualifies_for_mini_lecture is True
    assert cluster.gso_id == "gso-1"
    assert cluster.items[0]["lecture_id"] == "lec-1"
    assert cluster.items[0]["user_id"] == "stu-0"


# --- reply --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_replies_to_student_in_cluster(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    payload = ReviewReplyCreate(cluster_ref="a", student_user_id="stu-1", body=" See p.12 ")
    await _service(world).reply(claims, "rev-1", payload)
    replies = [o for o in world.added if isinstance(o, ReviewReply)]
    assert len(replies) == 1
    assert replies[0].student_user_id == "stu-1"
    assert replies[0].cluster_id == "a"
    assert replies[0].body == "See p.12"
    assert ACTION_REPLY in world.review.acted_actions


@pytest.mark.asyncio
async def test_reply_to_student_outside_cluster_rejected(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    payload = ReviewReplyCreate(cluster_ref="a", student_user_id="stu-99", body="hi")
    with pytest.raises(ValidationError):
        await _service(world).reply(claims, "rev-1", payload)


@pytest.mark.asyncio
async def test_unknown_cluster_is_404(world: World, as_user: Any) -> None:
    claims = as_user(world.teacher)
    payload = ReviewReplyCreate(cluster_ref="zzz", student_user_id="stu-0", body="hi")
    with pytest.raises(NotFoundError):
        await _service(world).reply(claims, "rev-1", payload)


@pytest.mark.asyncio
async def test_coordinator_cannot_reply(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.COORDINATOR, "coord-1"))
    payload = ReviewReplyCreate(cluster_ref="a", student_user_id="stu-0", body="hi")
    with pytest.raises(PermissionDeniedError):
        await _service(world).reply(claims, "rev-1", payload)


# --- skip ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_writes_row_and_audits(world: World, as_user: Any, _quiet: AsyncMock) -> None:
    claims = as_user(world.teacher)
    await _service(world).skip(claims, "rev-1", "b")
    rows = [o for o in world.added if isinstance(o, SkippedCluster)]
    assert [r.cluster_ref for r in rows] == ["b"]
    assert ACTION_SKIP in world.review.acted_actions
    assert _quiet.await_args is not None
    assert _quiet.await_args.kwargs["action"] == REVIEW_CLUSTER_SKIPPED


@pytest.mark.asyncio
async def test_skip_is_idempotent(
    world: World, as_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    claims = as_user(world.teacher)
    monkeypatch.setattr(
        "app.features.next_day_review.service.skipped_refs", AsyncMock(return_value={"b"})
    )
    await _service(world).skip(claims, "rev-1", "b")
    assert not [o for o in world.added if isinstance(o, SkippedCluster)]


@pytest.mark.asyncio
async def test_admin_cannot_skip_for_teacher(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.SCHOOL_ADMIN, "admin-1"))
    with pytest.raises(PermissionDeniedError):
        await _service(world).skip(claims, "rev-1", "a")


# --- regenerate ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_enqueues_task(
    world: World, as_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.next_day_review.tasks.regenerate_mini.apply_async", apply_async
    )
    claims = as_user(world.teacher)
    await _service(world).regenerate_mini(claims, "rev-1")
    apply_async.assert_called_once_with(kwargs={"school_id": "school-1", "review_id": "rev-1"})


@pytest.mark.asyncio
async def test_regenerate_refused_when_everything_skipped(
    world: World, as_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.next_day_review.tasks.regenerate_mini.apply_async", apply_async
    )
    world.execute_rows = ["a", "b"]
    claims = as_user(world.teacher)
    with pytest.raises(ValidationError):
        await _service(world).regenerate_mini(claims, "rev-1")
    apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_admin_regenerate_is_audited_override(
    world: World, as_user: Any, monkeypatch: pytest.MonkeyPatch, _quiet: AsyncMock
) -> None:
    monkeypatch.setattr(
        "app.features.next_day_review.tasks.regenerate_mini.apply_async", MagicMock()
    )
    claims = as_user(make_user(UserRole.SCHOOL_ADMIN, "admin-1"))
    await _service(world).regenerate_mini(claims, "rev-1")
    assert _quiet.await_args is not None
    assert _quiet.await_args.kwargs["action"] == REVIEW_OVERRIDE_ACTION


@pytest.mark.asyncio
async def test_regenerate_review_mini_targets_unskipped_and_updates_card(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    world.execute_rows = ["a"]  # critical cluster "a" skipped → "b" is the target
    generate = AsyncMock(
        return_value={"lecture_id": "mini-2", "cluster_ref": "b", "status": "generated"}
    )
    monkeypatch.setattr(regeneration, "generate_mini_for_cluster", generate)

    result = await regenerate_review_mini(world.session(), review_id="rev-1")

    assert result is not None and result["lecture_id"] == "mini-2"
    assert generate.await_args is not None
    assert generate.await_args.kwargs["cluster"].cluster_ref == "b"
    assert world.review.mini_lecture_id == "mini-2"
    by_ref = {c["cluster_ref"]: c for c in world.review.clusters_jsonb}
    assert by_ref["b"]["mini_lecture_id"] == "mini-2"
    assert by_ref["a"]["mini_lecture_id"] == "mini-1"
