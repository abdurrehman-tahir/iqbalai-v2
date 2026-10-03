"""T-192 — optional lecture rating: 5% of the quality score, anonymous, never ranking."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError, setup_exception_handlers
from app.db.base import Base
from app.features.audit.actions import LECTURE_RATING_SUBMITTED, REGISTERED_AUDIT_ACTIONS
from app.features.audit.models import AuditLogEntry
from app.features.lecture_ratings.models import SchoolLectureRating
from app.features.lecture_ratings.schemas import LectureRatingSummaryRead, MyLectureRatingRead
from app.features.lecture_ratings.service import MIN_RATINGS_FOR_DISPLAY, LectureRatingService
from app.features.lectures.models import SchoolLectureVersion
from app.features.lectures.scoring import (
    AI_SCORE_WEIGHT,
    MAX_TOTAL_SCORE,
    STUDENT_RATING_WEIGHT,
    blended_quality_score,
)
from app.features.schools.models import District, School
from app.features.student_highlights.tests.pg_support import (
    Seed,
    make_user,
    requires_pg,
    seed_lecture,
)
from app.features.users.models import User, UserRole

_VERSIONS = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school"
_FEATURES = Path(__file__).resolve().parents[2]

# --- pure: 95 / 5 blend into the M-10 score --------------------------------------------


def test_weights_are_95_5() -> None:
    assert STUDENT_RATING_WEIGHT == pytest.approx(0.05)
    assert AI_SCORE_WEIGHT == pytest.approx(0.95)


def test_blend_math() -> None:
    # AI 44/55 = 80%; rating avg 5 → 100%  →  0.95*80 + 0.05*100 = 81.0
    assert blended_quality_score(44, 5.0) == 81.0
    # rating avg 1 → 0%  →  0.95*80 = 76.0
    assert blended_quality_score(44, 1.0) == 76.0
    # no eligible rating average → AI score alone
    assert blended_quality_score(44, None) == 80.0
    assert blended_quality_score(None, 4.0) is None
    assert blended_quality_score(MAX_TOTAL_SCORE, 3.0) == 97.5


def test_rating_moves_score_by_at_most_five_points() -> None:
    best = blended_quality_score(30, 5.0)
    worst = blended_quality_score(30, 1.0)
    assert best is not None and worst is not None
    assert best - worst == pytest.approx(5.0)


def test_table_shape_and_constraints() -> None:
    table = Base.metadata.tables["school.lecture_ratings"]
    fks = {fk.parent.name: fk.ondelete for fk in table.foreign_keys}
    assert fks["lecture_id"] == "CASCADE"  # ARCH §4.6 locked
    assert fks["student_user_id"] == "CASCADE"
    text = (_VERSIONS / "0079_lecture_ratings.py").read_text(encoding="utf-8")
    assert "rating BETWEEN 1 AND 5" in text
    assert "lecture_ratings_lecture_student_uq" in text


def test_audit_action_registered() -> None:
    assert LECTURE_RATING_SUBMITTED in REGISTERED_AUDIT_ACTIONS


def test_ratings_never_reach_any_student_ranking_surface() -> None:
    """Coaching, not grading: no feature other than lecture_ratings reads ratings."""
    offenders: list[str] = []
    pattern = re.compile(r"lecture_ratings\.(models|repository|service)")
    for path in _FEATURES.rglob("*.py"):
        rel = path.relative_to(_FEATURES).as_posix()
        if rel.startswith("lecture_ratings/") or "/tests/" in rel:
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []


def test_student_schema_exposes_only_own_rating() -> None:
    assert set(MyLectureRatingRead.model_fields) == {"lecture_id", "rating"}
    assert "student_user_id" not in LectureRatingSummaryRead.model_fields


# --- real Postgres ---------------------------------------------------------------------


async def _claims(pg: AsyncSession, user_id: str) -> dict[str, object]:
    user = await pg.get(User, user_id)
    assert user is not None
    return {"sub": user.authentik_id, "role": user.role.value}


def _svc(pg: AsyncSession, *, can_access: bool = True) -> LectureRatingService:
    svc = LectureRatingService(pg)
    svc._lecture_svc = MagicMock()
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=can_access)
    return svc


async def _score_current_version(pg: AsyncSession, seed: Seed, total: int) -> None:
    version = await pg.get(SchoolLectureVersion, seed.version_id)
    assert version is not None
    version.scores_jsonb = {"total": total}
    await pg.flush()


async def _rate(pg: AsyncSession, seed: Seed, value: int) -> str:
    student = await make_user(pg, role=UserRole.STUDENT, school_id=seed.school_id)
    await _svc(pg).submit(await _claims(pg, student.id), seed.lecture_id, value)
    return student.id


@requires_pg
async def test_submit_upserts_one_rating_per_student_and_audits(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    claims = await _claims(pg, seed.student_id)
    assert (await _svc(pg).get_mine(claims, seed.lecture_id)).rating is None

    await _svc(pg).submit(claims, seed.lecture_id, 4)
    await _svc(pg).submit(claims, seed.lecture_id, 2)

    rows = (
        (
            await pg.execute(
                select(SchoolLectureRating).where(SchoolLectureRating.lecture_id == seed.lecture_id)
            )
        )
        .scalars()
        .all()
    )
    assert [(r.student_user_id, r.rating) for r in rows] == [(seed.student_id, 2)]
    assert rows[0].lecture_version_id == seed.version_id
    assert (await _svc(pg).get_mine(claims, seed.lecture_id)).rating == 2

    audits = (
        (
            await pg.execute(
                select(AuditLogEntry).where(
                    AuditLogEntry.action == LECTURE_RATING_SUBMITTED,
                    AuditLogEntry.target_id == seed.lecture_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 2
    assert all(a.actor_id == seed.student_id for a in audits)
    # The audit trail must not carry the value (would de-anonymise ratings).
    assert all(a.metadata_json is None for a in audits)


@requires_pg
async def test_db_rejects_out_of_range_rating(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    with pytest.raises(IntegrityError):
        async with pg.begin_nested():
            pg.add(
                SchoolLectureRating(
                    lecture_id=seed.lecture_id, student_user_id=seed.student_id, rating=6
                )
            )
            await pg.flush()


@requires_pg
async def test_students_never_see_each_others_ratings(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    await _svc(pg).submit(await _claims(pg, seed.student_id), seed.lecture_id, 5)
    other = await _svc(pg).get_mine(await _claims(pg, seed.other_student_id), seed.lecture_id)
    assert other.rating is None


@requires_pg
async def test_student_without_access_cannot_rate(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    with pytest.raises(PermissionDeniedError):
        await _svc(pg, can_access=False).submit(
            await _claims(pg, seed.student_id), seed.lecture_id, 3
        )


@requires_pg
async def test_teacher_sees_anonymous_average_only_above_threshold(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    await _score_current_version(pg, seed, 44)  # 80% AI
    teacher = await _claims(pg, seed.teacher_id)

    await _rate(pg, seed, 5)
    below = await _svc(pg).summary(teacher, seed.lecture_id)
    assert below.rating_count == 1
    assert below.average_rating is None  # one rating would be identifiable
    assert below.quality_score == 80.0  # AI only until the average is shown

    for value in (5, 5):
        await _rate(pg, seed, value)
    above = await _svc(pg).summary(teacher, seed.lecture_id)
    assert above.rating_count == MIN_RATINGS_FOR_DISPLAY == 3
    assert above.average_rating == 5.0
    assert above.ai_score == 44 and above.ai_score_max == 55
    assert above.quality_score == 81.0  # 0.95*80 + 0.05*100
    assert above.rating_weight == pytest.approx(0.05)
    assert set(above.model_dump()) == set(LectureRatingSummaryRead.model_fields)


@requires_pg
async def test_other_teacher_and_students_cannot_read_summary(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    stranger = await make_user(pg, role=UserRole.TEACHER, school_id=seed.school_id)
    with pytest.raises(NotFoundError):
        await _svc(pg).summary(await _claims(pg, stranger.id), seed.lecture_id)
    with pytest.raises(PermissionDeniedError):
        await _svc(pg).summary(await _claims(pg, seed.student_id), seed.lecture_id)


@requires_pg
async def test_coordinator_same_school_and_district_admin_scoping(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    coordinator = await make_user(pg, role=UserRole.COORDINATOR, school_id=seed.school_id)
    assert (await _svc(pg).summary(await _claims(pg, coordinator.id), seed.lecture_id)).lecture_id

    district = District(name="Elsewhere")
    pg.add(district)
    await pg.flush()
    other_school = School(name="Other", district_id=district.id)
    pg.add(other_school)
    await pg.flush()
    foreign = await make_user(pg, role=UserRole.COORDINATOR, school_id=other_school.id)
    with pytest.raises(NotFoundError):
        await _svc(pg).summary(await _claims(pg, foreign.id), seed.lecture_id)

    school = await pg.get(School, seed.school_id)
    assert school is not None
    dist_admin = await make_user(pg, role=UserRole.DISTRICT_ADMIN, school_id=None)
    dist_admin.district_id = school.district_id
    await pg.flush()
    assert (await _svc(pg).summary(await _claims(pg, dist_admin.id), seed.lecture_id)).lecture_id


# --- API contract ---------------------------------------------------------------------


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client(role: str) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db

    async def _c() -> dict[str, object]:
        return {"sub": "auth-1", "role": role}

    app.dependency_overrides[get_current_user] = _c
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_rating_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    mine = MyLectureRatingRead(lecture_id="lec-1", rating=4)
    submit = AsyncMock(return_value=mine)
    monkeypatch.setattr(LectureRatingService, "get_mine", AsyncMock(return_value=mine))
    monkeypatch.setattr(LectureRatingService, "submit", submit)
    summary: Any = LectureRatingSummaryRead(
        lecture_id="lec-1",
        rating_count=3,
        min_ratings_for_display=3,
        average_rating=4.0,
        ai_score=44,
        ai_score_max=55,
        quality_score=79.75,
        rating_weight=0.05,
    )
    monkeypatch.setattr(LectureRatingService, "summary", AsyncMock(return_value=summary))

    async with _client("student") as client:
        got = await client.get("/api/v1/students/me/lectures/lec-1/rating")
        ok = await client.put("/api/v1/students/me/lectures/lec-1/rating", json={"rating": 4})
        bad = await client.put("/api/v1/students/me/lectures/lec-1/rating", json={"rating": 6})
        zero = await client.put("/api/v1/students/me/lectures/lec-1/rating", json={"rating": 0})
        denied = await client.get("/api/v1/lectures/lec-1/rating-summary")
    async with _client("teacher") as client:
        teacher = await client.get("/api/v1/lectures/lec-1/rating-summary")

    assert got.status_code == 200 and ok.status_code == 200
    MyLectureRatingRead.model_validate(ok.json()["data"])
    assert submit.await_args is not None and submit.await_args.args[2] == 4
    assert bad.status_code == 422 and zero.status_code == 422
    assert denied.status_code == 403  # students never reach the aggregate route
    assert teacher.status_code == 200
    LectureRatingSummaryRead.model_validate(teacher.json()["data"])
