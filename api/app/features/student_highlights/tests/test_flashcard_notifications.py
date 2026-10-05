"""T-193 — nightly flashcard batch notification (flow-6 §7, ARCH §10.6 / §9.21)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.notifications.models import Notification
from app.features.student_highlights.flashcard_notifications import (
    TEMPLATE_KEY,
    batch_window,
    send_flashcard_batch,
)
from app.features.student_highlights.models import SchoolStudentFlashcard
from app.features.student_highlights.tests.pg_support import Seed, requires_pg, seed_lecture
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User
from app.infrastructure.notifications.templates.self_study import (
    SELF_STUDY_TEMPLATES,
    TEMPLATE_CHANNELS,
    render_self_study_template,
)
from app.tasks.beat_schedule import BEAT_SCHEDULE

RUN = datetime(2026, 10, 3, 18, 15, tzinfo=timezone.utc)


def test_window_ends_at_last_scheduled_boundary() -> None:
    start, end = batch_window(RUN + timedelta(minutes=2))
    assert end == RUN and start == RUN - timedelta(days=1)
    start, end = batch_window(RUN - timedelta(minutes=1))
    assert end == RUN - timedelta(days=1)


def test_template_in_four_locales_in_app_only() -> None:
    variants = SELF_STUDY_TEMPLATES[TEMPLATE_KEY]["default"]
    assert set(variants) == {"en", "ur", "sd", "ps"}
    assert TEMPLATE_CHANNELS[TEMPLATE_KEY] == frozenset({"in_app"})
    assert (
        "3 new flashcard" in render_self_study_template(TEMPLATE_KEY, params={"count": "3"})["body"]
    )
    for loc in ("ur", "sd", "ps"):
        body = render_self_study_template(TEMPLATE_KEY, locale=loc, params={"count": "3"})["body"]
        assert "3" in body and "__TODO__" not in body


def test_beat_and_task_registered_per_arch_10_6() -> None:
    from app.features.student_highlights.tasks import batch_notification

    entry: Any = BEAT_SCHEDULE["batch-flashcard-notifications"]
    assert entry["task"] == "flashcards.batch_notification"
    assert entry["schedule"].hour == {18} and entry["schedule"].minute == {15}
    assert batch_notification.name == "flashcards.batch_notification"
    assert batch_notification.queue == "notifications"


async def _card(
    pg: AsyncSession, seed: Seed, student_id: str, at: datetime, n: int, **kw: Any
) -> None:
    card = SchoolStudentFlashcard(
        student_user_id=student_id,
        lecture_id=seed.lecture_id,
        front_text=f"front {n}",
        back_text="back",
        dedupe_hash=f"{n:064d}",
        created_at=at,
        **kw,
    )
    pg.add(card)
    await pg.flush()


async def _notifications(pg: AsyncSession, authentik_id: str) -> list[Notification]:
    return list(
        (
            await pg.execute(
                select(Notification).where(
                    Notification.recipient_user_id == authentik_id,
                    Notification.template_key == TEMPLATE_KEY,
                )
            )
        )
        .scalars()
        .all()
    )


@requires_pg
async def test_one_batched_notification_per_student_and_idempotent(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    inside = RUN - timedelta(hours=3)
    for n in range(3):
        await _card(pg, seed, seed.student_id, inside, n)
    await _card(pg, seed, seed.student_id, RUN - timedelta(days=2), 9)  # previous window
    await _card(pg, seed, seed.student_id, inside, 10, deleted_at=inside)  # deleted
    await _card(pg, seed, seed.other_student_id, inside, 20)
    pg.add(
        StudentProfile(user_id=seed.other_student_id, display_name="O", language_preference="ur")
    )
    await pg.flush()

    sent = await send_flashcard_batch(pg, now=RUN + timedelta(minutes=1))
    assert sent >= 2

    me = await pg.get(User, seed.student_id)
    other = await pg.get(User, seed.other_student_id)
    assert me is not None and other is not None
    mine = await _notifications(pg, me.authentik_id)
    assert len(mine) == 1  # batched — not one per card
    assert mine[0].feature_namespace == "self_study"
    assert "3 new flashcard" in mine[0].body  # only live cards inside the window
    assert mine[0].school_id == seed.school_id
    theirs = await _notifications(pg, other.authentik_id)
    assert len(theirs) == 1 and "1" in theirs[0].body
    assert "فلیش کارڈ" in theirs[0].body  # student's Urdu preference

    # A retried run for the same window sends nothing new.
    await send_flashcard_batch(pg, now=RUN + timedelta(minutes=5))
    assert len(await _notifications(pg, me.authentik_id)) == 1


@requires_pg
async def test_no_cards_no_notification(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    await send_flashcard_batch(pg, now=RUN + timedelta(minutes=1))
    me = await pg.get(User, seed.student_id)
    assert me is not None
    assert await _notifications(pg, me.authentik_id) == []


@pytest.mark.parametrize("hour", [0, 18, 23])
def test_window_is_always_24h(hour: int) -> None:
    start, end = batch_window(datetime(2026, 10, 3, hour, 30, tzinfo=timezone.utc))
    assert end - start == timedelta(days=1)
