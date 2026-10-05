"""T-188 — My Highlights / flashcards (flow-6 §3.6 / §4 / §5.5, ARCH §6.19)."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError, setup_exception_handlers
from app.features.schools.models import District, School
from app.features.student_highlights import my_highlights as mh
from app.features.student_highlights.flashcards import ensure_flashcard_for_highlight
from app.features.student_highlights.models import SchoolStudentFlashcard, SchoolStudentHighlight
from app.features.student_highlights.my_highlights import MyHighlightsService
from app.features.student_highlights.schemas import (
    HighlightLectureRefRead,
    LectureHighlightAggregateRead,
    MyHighlightRead,
    PairedFlashcardRead,
)
from app.features.student_highlights.tests.pg_support import (
    Seed,
    make_question,
    make_user,
    requires_pg,
    seed_lecture,
)
from app.features.users.models import UserRole


async def _claims(pg: AsyncSession, user_id: str) -> dict[str, object]:
    from app.features.users.models import User

    user = await pg.get(User, user_id)
    assert user is not None
    return {"sub": user.authentik_id, "role": user.role.value, "user_id": user.id}


async def _highlight_with_card(
    pg: AsyncSession,
    seed: Seed,
    *,
    text: str = "mass",
    student_id: str | None = None,
    answer: str = "Mass is matter.",
    created_at: datetime | None = None,
) -> tuple[SchoolStudentHighlight, SchoolStudentFlashcard]:
    sid = student_id or seed.student_id
    q = await make_question(pg, seed, student_id=sid, highlight_text=text)
    hl = SchoolStudentHighlight(
        student_user_id=sid,
        lecture_id=seed.lecture_id,
        paragraph_id=seed.paragraph_id,
        paragraph_ordinal=0,
        text_range_offset=max(0, seed.paragraph_text.find(text)),
        text_range_length=len(text),
        highlighted_text=text,
        question_id=q.id,
        concept_tag="forces/newton-2",
    )
    if created_at is not None:
        hl.created_at = created_at
    pg.add(hl)
    await pg.flush()
    card, _ = await ensure_flashcard_for_highlight(
        pg, highlight=hl, answer_text=answer, answer_ok=True
    )
    return hl, card


# --- student feed ---------------------------------------------------------------


@requires_pg
async def test_feed_lists_own_highlights_newest_first_with_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    t0 = datetime.now(timezone.utc)
    await _highlight_with_card(pg, seed, text="mass", created_at=t0 - timedelta(minutes=5))
    await _highlight_with_card(pg, seed, text="acceleration", created_at=t0)
    # Another student's highlight must never appear.
    await _highlight_with_card(pg, seed, text="Force", student_id=seed.other_student_id)

    items, total = await MyHighlightsService(pg).list_mine(
        await _claims(pg, seed.student_id), page=1, page_size=20
    )

    assert total == 2
    assert [i.highlighted_text for i in items] == ["acceleration", "mass"]
    first = items[0]
    assert first.lecture.id == seed.lecture_id and first.lecture.title == "Newton"
    assert first.concept_tag == "forces/newton-2"
    assert first.paragraph_ordinal == 0
    assert first.flashcard is not None
    assert first.flashcard.front_text == "acceleration"
    assert first.flashcard.back_is_placeholder is False


@requires_pg
async def test_repeat_highlight_shows_the_shared_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    _, card = await _highlight_with_card(pg, seed, text="mass")
    await _highlight_with_card(pg, seed, text="mass", answer="ignored — deduped")

    items, _ = await MyHighlightsService(pg).list_mine(
        await _claims(pg, seed.student_id), page=1, page_size=20
    )
    assert len(items) == 2
    assert {i.flashcard.id for i in items if i.flashcard} == {card.id}


@requires_pg
async def test_feed_pagination(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    for word in ("Force", "mass", "acceleration"):
        await _highlight_with_card(pg, seed, text=word)
    claims = await _claims(pg, seed.student_id)
    page1, total = await MyHighlightsService(pg).list_mine(claims, page=1, page_size=2)
    page2, _ = await MyHighlightsService(pg).list_mine(claims, page=2, page_size=2)
    assert total == 3 and len(page1) == 2 and len(page2) == 1
    assert {i.id for i in page1}.isdisjoint({i.id for i in page2})


@requires_pg
async def test_non_student_cannot_list(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    with pytest.raises(PermissionDeniedError):
        await MyHighlightsService(pg).list_mine(
            await _claims(pg, seed.teacher_id), page=1, page_size=20
        )


# --- edit / delete -----------------------------------------------------------------


@requires_pg
async def test_student_edits_own_card_back(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    _, card = await _highlight_with_card(pg, seed)
    card.back_text = ""  # placeholder (failed answer)
    await pg.flush()

    out = await MyHighlightsService(pg).update_flashcard_back(
        await _claims(pg, seed.student_id), flashcard_id=card.id, back_text="  My own note  "
    )
    assert out.back_text == "My own note" and out.back_is_placeholder is False


@requires_pg
async def test_other_student_cannot_edit_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    _, card = await _highlight_with_card(pg, seed)
    with pytest.raises(NotFoundError):
        await MyHighlightsService(pg).update_flashcard_back(
            await _claims(pg, seed.other_student_id), flashcard_id=card.id, back_text="hijack"
        )


@requires_pg
async def test_delete_highlight_soft_deletes_its_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    hl, card = await _highlight_with_card(pg, seed)
    await MyHighlightsService(pg).delete_highlight(
        await _claims(pg, seed.student_id), highlight_id=hl.id
    )
    assert hl.deleted_at is not None
    assert card.deleted_at is not None
    items, total = await MyHighlightsService(pg).list_mine(
        await _claims(pg, seed.student_id), page=1, page_size=20
    )
    assert total == 0 and items == []


@requires_pg
async def test_delete_keeps_card_still_paired_with_another_highlight(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    first, card = await _highlight_with_card(pg, seed, text="mass")
    await _highlight_with_card(pg, seed, text="mass")
    await MyHighlightsService(pg).delete_highlight(
        await _claims(pg, seed.student_id), highlight_id=first.id
    )
    assert card.deleted_at is None


@requires_pg
async def test_cannot_delete_another_students_highlight(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    hl, _ = await _highlight_with_card(pg, seed)
    with pytest.raises(NotFoundError):
        await MyHighlightsService(pg).delete_highlight(
            await _claims(pg, seed.other_student_id), highlight_id=hl.id
        )


# --- parent (read-only, #72) ----------------------------------------------------


def _link_state(linked: bool) -> MagicMock:
    svc = MagicMock()
    svc.get_parent_student_access_state = AsyncMock(return_value=MagicMock(read_only_access=linked))
    return MagicMock(return_value=svc)


@requires_pg
async def test_parent_with_link_and_sharing_reads_child_feed(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    await _highlight_with_card(pg, seed)
    monkeypatch.setattr(mh, "ParentChildLinkService", _link_state(True))
    monkeypatch.setattr(mh, "student_allows_teacher_share", AsyncMock(return_value=True))
    items, total = await MyHighlightsService(pg).list_for_parent(
        {"sub": "parent", "role": "parent"},
        student_user_id=seed.student_id,
        page=1,
        page_size=20,
    )
    assert total == 1 and items[0].highlighted_text == "mass"


@requires_pg
async def test_parent_sees_nothing_when_child_opted_out(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    await _highlight_with_card(pg, seed)
    monkeypatch.setattr(mh, "ParentChildLinkService", _link_state(True))
    monkeypatch.setattr(mh, "student_allows_teacher_share", AsyncMock(return_value=False))
    items, total = await MyHighlightsService(pg).list_for_parent(
        {"sub": "parent"}, student_user_id=seed.student_id, page=1, page_size=20
    )
    assert (items, total) == ([], 0)


@pytest.mark.asyncio
async def test_parent_without_link_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mh, "ParentChildLinkService", _link_state(False))
    with pytest.raises(PermissionDeniedError):
        await MyHighlightsService(AsyncMock()).list_for_parent(
            {"sub": "parent"}, student_user_id="stu-x", page=1, page_size=20
        )


# --- coordinator / admin aggregate ---------------------------------------------


@requires_pg
async def test_coordinator_gets_anonymous_aggregate_for_own_school(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    await _highlight_with_card(pg, seed, text="mass")
    await _highlight_with_card(pg, seed, text="mass")
    await _highlight_with_card(pg, seed, text="Force", student_id=seed.other_student_id)
    coordinator = await make_user(pg, role=UserRole.COORDINATOR, school_id=seed.school_id)
    monkeypatch.setattr(mh, "student_allows_teacher_share", AsyncMock(return_value=True))

    agg = await MyHighlightsService(pg).lecture_aggregate(
        await _claims(pg, coordinator.id), lecture_id=seed.lecture_id
    )
    assert agg.highlight_count == 3
    assert agg.student_count == 2
    assert agg.flashcard_count == 2  # repeat highlight shares one card
    assert agg.top_concepts[0].concept_tag == "forces/newton-2"
    dumped = agg.model_dump()
    assert set(dumped) == {
        "lecture_id",
        "highlight_count",
        "student_count",
        "flashcard_count",
        "top_concepts",
    }  # no text, no student ids


@requires_pg
async def test_aggregate_excludes_students_who_opted_out(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    await _highlight_with_card(pg, seed, text="mass")
    await _highlight_with_card(pg, seed, text="Force", student_id=seed.other_student_id)
    admin = await make_user(pg, role=UserRole.SCHOOL_ADMIN, school_id=seed.school_id)

    async def _shares(_s: Any, student_id: str) -> bool:
        return student_id == seed.student_id

    monkeypatch.setattr(mh, "student_allows_teacher_share", _shares)
    agg = await MyHighlightsService(pg).lecture_aggregate(
        await _claims(pg, admin.id), lecture_id=seed.lecture_id
    )
    assert (agg.highlight_count, agg.student_count) == (1, 1)


@requires_pg
async def test_coordinator_of_another_school_gets_404(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    district = District(name="Other District")
    pg.add(district)
    await pg.flush()
    other_school = School(name="Other School", district_id=district.id)
    pg.add(other_school)
    await pg.flush()
    stranger = await make_user(pg, role=UserRole.COORDINATOR, school_id=other_school.id)
    with pytest.raises(NotFoundError):
        await MyHighlightsService(pg).lecture_aggregate(
            await _claims(pg, stranger.id), lecture_id=seed.lecture_id
        )


@requires_pg
async def test_district_admin_scoped_to_own_district(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    school = await pg.get(School, seed.school_id)
    assert school is not None
    own = await make_user(pg, role=UserRole.DISTRICT_ADMIN, school_id=None)
    own.district_id = school.district_id
    other = await make_user(pg, role=UserRole.DISTRICT_ADMIN, school_id=None)
    other.district_id = "district-elsewhere"
    await pg.flush()

    agg = await MyHighlightsService(pg).lecture_aggregate(
        await _claims(pg, own.id), lecture_id=seed.lecture_id
    )
    assert agg.lecture_id == seed.lecture_id
    with pytest.raises(NotFoundError):
        await MyHighlightsService(pg).lecture_aggregate(
            await _claims(pg, other.id), lecture_id=seed.lecture_id
        )


@requires_pg
async def test_teacher_and_student_cannot_read_aggregate(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    for uid in (seed.teacher_id, seed.student_id):
        with pytest.raises(PermissionDeniedError):
            await MyHighlightsService(pg).lecture_aggregate(
                await _claims(pg, uid), lecture_id=seed.lecture_id
            )


# --- API contract -----------------------------------------------------------------


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client(role: str) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db

    async def _c() -> dict[str, object]:
        return {"sub": "auth-1", "role": role, "user_id": "u-1"}

    app.dependency_overrides[get_current_user] = _c
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _item() -> MyHighlightRead:
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    return MyHighlightRead(
        id="h-1",
        highlighted_text="mass",
        concept_tag="forces",
        created_at=now,
        lecture=HighlightLectureRefRead(id="lec-1", title="Newton", topic="Forces"),
        paragraph_ordinal=0,
        question_id="q-1",
        flashcard=PairedFlashcardRead(
            id="fc-1",
            front_text="mass",
            back_text="",
            back_is_placeholder=True,
            status="active",
            concept_tag="forces",
            created_at=now,
        ),
    )


@pytest.mark.asyncio
async def test_api_my_highlights_paginated_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MyHighlightsService, "list_mine", AsyncMock(return_value=([_item()], 1)))
    async with _client("student") as client:
        res = await client.get("/api/v1/students/me/highlights?page=1&page_size=20")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1 and body["page"] == 1 and body["pages"] == 1
    MyHighlightRead.model_validate(body["items"][0])


@pytest.mark.asyncio
async def test_api_page_size_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    async with _client("student") as client:
        res = await client.get("/api/v1/students/me/highlights?page_size=1000")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_api_patch_flashcard_validates_and_returns_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = _item().flashcard
    monkeypatch.setattr(MyHighlightsService, "update_flashcard_back", AsyncMock(return_value=card))
    async with _client("student") as client:
        bad = await client.patch("/api/v1/students/me/flashcards/fc-1", json={"back_text": ""})
        ok = await client.patch("/api/v1/students/me/flashcards/fc-1", json={"back_text": "x"})
    assert bad.status_code == 422
    assert ok.status_code == 200
    PairedFlashcardRead.model_validate(ok.json()["data"])


@pytest.mark.asyncio
async def test_api_delete_highlight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MyHighlightsService, "delete_highlight", AsyncMock(return_value=None))
    async with _client("student") as client:
        res = await client.delete("/api/v1/students/me/highlights/h-1")
    assert res.status_code == 200 and res.json()["data"] == {"deleted": True}


@pytest.mark.asyncio
async def test_api_parent_route_and_aggregate_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MyHighlightsService, "list_for_parent", AsyncMock(return_value=([], 0)))
    monkeypatch.setattr(
        MyHighlightsService,
        "lecture_aggregate",
        AsyncMock(
            return_value=LectureHighlightAggregateRead(
                lecture_id="lec-1",
                highlight_count=0,
                student_count=0,
                flashcard_count=0,
                top_concepts=[],
            )
        ),
    )
    async with _client("parent") as client:
        parent = await client.get("/api/v1/parents/me/students/stu-1/highlights")
        # A parent is below coordinator → the aggregate route is refused up front.
        denied = await client.get("/api/v1/school/lectures/lec-1/highlight-aggregate")
    async with _client("coordinator") as client:
        agg = await client.get("/api/v1/school/lectures/lec-1/highlight-aggregate")
    assert parent.status_code == 200 and parent.json()["items"] == []
    assert denied.status_code == 403
    assert agg.status_code == 200
    LectureHighlightAggregateRead.model_validate(agg.json()["data"])
