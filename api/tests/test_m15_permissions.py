"""T-193 — M-15 permission matrix, enforced at the API (not just the UI).

Real requests through the full v1 router against real Postgres (DB_URL), with
seeded users of every relevant role. Flow-6 §4 + ARCH §6.19:

- Student owns highlights / flashcards / sim progress / ratings — no other
  role can use the student routes, and no student can read another's data.
- Parent: read-only, approved link + #72 required (no link → denied).
- Coordinator / Admin: anonymous aggregates within scope only.
- Teacher: rating aggregate for OWN lecture only; never individual ratings.
- Wrong school / wrong tenant (independent claims) → denied.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.schools.models import District, School
from app.features.student_highlights.tests.pg_support import make_user, requires_pg, seed_lecture
from app.features.users.models import User, UserRole

pytestmark = requires_pg


@asynccontextmanager
async def _client(pg: AsyncSession, claims: dict[str, object]) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")

    async def _db() -> AsyncGenerator[AsyncSession, None]:
        yield pg

    async def _claims() -> dict[str, object]:
        return claims

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _claims
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _claims_for(user: User) -> dict[str, object]:
    return {
        "sub": user.authentik_id,
        "role": user.role.value,
        "user_id": user.id,
        "tenant_type": "school",
    }


def _student_routes(lecture_id: str) -> list[tuple[str, str, dict[str, object] | None]]:
    return [
        ("GET", f"/api/v1/students/me/lectures/{lecture_id}/highlights", None),
        ("GET", "/api/v1/students/me/highlights", None),
        ("PATCH", "/api/v1/students/me/flashcards/fc-x", {"back_text": "x"}),
        ("DELETE", "/api/v1/students/me/highlights/h-x", None),
        ("GET", f"/api/v1/students/me/lectures/{lecture_id}/concepts", None),
        ("GET", f"/api/v1/students/me/lectures/{lecture_id}/enrichment?concept_id=Forces", None),
        ("GET", f"/api/v1/students/me/lectures/{lecture_id}/simulation?concept_id=Forces", None),
        ("GET", f"/api/v1/students/me/lectures/{lecture_id}/rating", None),
        ("PUT", f"/api/v1/students/me/lectures/{lecture_id}/rating", {"rating": 3}),
    ]


@pytest.mark.parametrize("role", [UserRole.TEACHER, UserRole.COORDINATOR, UserRole.PARENT])
async def test_non_students_cannot_use_student_routes(pg: AsyncSession, role: UserRole) -> None:
    seed = await seed_lecture(pg)
    user = await make_user(pg, role=role, school_id=seed.school_id)
    async with _client(pg, _claims_for(user)) as client:
        for method, url, body in _student_routes(seed.lecture_id):
            res = await client.request(method, url, json=body)
            assert res.status_code in (403, 404), f"{role.value} {method} {url} → {res.status_code}"


async def test_unenrolled_student_cannot_read_lecture_artifacts(pg: AsyncSession) -> None:
    """A student outside the lecture's GSO (here: another school) is denied by the
    real access gate — not by the UI."""
    seed = await seed_lecture(pg)
    district = District(name="D2")
    pg.add(district)
    await pg.flush()
    school = School(name="S2", district_id=district.id)
    pg.add(school)
    await pg.flush()
    outsider = await make_user(pg, role=UserRole.STUDENT, school_id=school.id)
    async with _client(pg, _claims_for(outsider)) as client:
        for method, url, body in _student_routes(seed.lecture_id):
            if "/lectures/" not in url:
                continue  # own-feed routes are owner-scoped, not lecture-gated
            res = await client.request(method, url, json=body)
            assert res.status_code == 403, f"{method} {url} → {res.status_code}"


async def test_independent_tenant_claims_cannot_reach_school_artifacts(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    claims = {
        "sub": "independent-sub-x",
        "role": "independent_student",
        "tenant_type": "independent",
    }
    async with _client(pg, claims) as client:
        for method, url, body in _student_routes(seed.lecture_id):
            res = await client.request(method, url, json=body)
            assert res.status_code in (403, 404), f"{method} {url} → {res.status_code}"


async def test_parent_without_link_is_denied(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    parent = await make_user(pg, role=UserRole.PARENT, school_id=None)
    async with _client(pg, _claims_for(parent)) as client:
        res = await client.get(f"/api/v1/parents/me/students/{seed.student_id}/highlights")
    # 422 = the existing parent-onboarding precondition (no parent profile) fires
    # before the link check; any of these is a denial with no data returned.
    assert res.status_code in (403, 404, 422)
    assert "items" not in res.json()


async def test_students_cannot_read_aggregates(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    student = await pg.get(User, seed.student_id)
    assert student is not None
    async with _client(pg, _claims_for(student)) as client:
        agg = await client.get(f"/api/v1/school/lectures/{seed.lecture_id}/highlight-aggregate")
        summary = await client.get(f"/api/v1/lectures/{seed.lecture_id}/rating-summary")
    assert agg.status_code == 403
    assert summary.status_code == 403


async def test_staff_aggregates_are_scoped_and_anonymous(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    teacher = await pg.get(User, seed.teacher_id)
    coordinator = await make_user(pg, role=UserRole.COORDINATOR, school_id=seed.school_id)
    other_teacher = await make_user(pg, role=UserRole.TEACHER, school_id=seed.school_id)
    assert teacher is not None

    async with _client(pg, _claims_for(teacher)) as client:
        own = await client.get(f"/api/v1/lectures/{seed.lecture_id}/rating-summary")
        # A teacher is not coordinator-level → no highlight aggregate.
        teacher_agg = await client.get(
            f"/api/v1/school/lectures/{seed.lecture_id}/highlight-aggregate"
        )
    async with _client(pg, _claims_for(other_teacher)) as client:
        not_own = await client.get(f"/api/v1/lectures/{seed.lecture_id}/rating-summary")
    async with _client(pg, _claims_for(coordinator)) as client:
        coord_agg = await client.get(
            f"/api/v1/school/lectures/{seed.lecture_id}/highlight-aggregate"
        )
        coord_summary = await client.get(f"/api/v1/lectures/{seed.lecture_id}/rating-summary")

    assert own.status_code == 200
    assert set(own.json()["data"]) == {
        "lecture_id",
        "rating_count",
        "min_ratings_for_display",
        "average_rating",
        "ai_score",
        "ai_score_max",
        "quality_score",
        "rating_weight",
    }  # aggregate only — no per-student ratings, no ids
    assert teacher_agg.status_code == 403
    assert not_own.status_code == 404
    assert coord_agg.status_code == 200 and coord_summary.status_code == 200
    assert "highlighted_text" not in coord_agg.text
