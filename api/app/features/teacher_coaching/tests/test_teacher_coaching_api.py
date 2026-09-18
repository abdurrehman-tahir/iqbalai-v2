"""T-138 — Teaching Innovation Record API tests (school tenant)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType
from app.features.users.models import User, UserAccountStatus, UserRole

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
OTHER_TEACHER = User(
    id="teacher-2",
    authentik_id="auth-teacher-2",
    email="teacher2@example.com",
    display_name="Teacher Two",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

PENDING = SchoolTeacherAiMemory(
    teacher_user_id="teacher-1",
    category="quality_dimension",
    weakness_type="originality",
    frequency=2,
    last_suggestion="Try grounding in local Punjab examples.",
    teacher_response=TeacherResponseType.NONE,
    created_at=datetime.now(timezone.utc),
)
PENDING.updated_at = datetime.now(timezone.utc)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeMemoryRepo:
    store: dict[str, SchoolTeacherAiMemory] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, memory_id: str) -> SchoolTeacherAiMemory | None:
        return self.store.get(memory_id)

    async def list_pending_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherAiMemory]:
        return [
            r
            for r in self.store.values()
            if r.teacher_user_id == teacher_user_id
            and r.teacher_response == TeacherResponseType.NONE
        ]

    async def update(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        return memory


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    PENDING.teacher_response = TeacherResponseType.NONE
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeMemoryRepo.store = {PENDING.id: PENDING}

    monkeypatch.setattr("app.features.teacher_coaching.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeMemoryRepo
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


async def _fake_other_user() -> dict[str, object]:
    return {"sub": "auth-teacher-2", "role": "teacher", "user_id": "teacher-2"}


def _make_client(current_user: Any) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = current_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_fake_user) as ac:
        yield ac


@pytest.fixture
async def other_client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_fake_other_user) as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_coaching_suggestions_returns_pending_only(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/coaching")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["weakness_type"] == "originality"
    assert items[0]["suggestion"] == "Try grounding in local Punjab examples."
    # Coaching framing only — no score/grade field anywhere in the response.
    assert "score" not in items[0]


@pytest.mark.asyncio
async def test_respond_marks_acted(client: AsyncClient) -> None:
    res = await client.post(
        f"/api/v1/teachers/me/coaching/{PENDING.id}/respond", json={"response": "acted"}
    )
    assert res.status_code == 200
    assert res.json()["data"]["weakness_type"] == "originality"
    assert PENDING.teacher_response == TeacherResponseType.ACTED


@pytest.mark.asyncio
async def test_respond_rejects_invalid_response_value(client: AsyncClient) -> None:
    res = await client.post(
        f"/api/v1/teachers/me/coaching/{PENDING.id}/respond", json={"response": "maybe"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_respond_to_others_suggestion_is_rejected(other_client: AsyncClient) -> None:
    res = await other_client.post(
        f"/api/v1/teachers/me/coaching/{PENDING.id}/respond", json={"response": "acted"}
    )
    assert res.status_code == 403
    assert PENDING.teacher_response == TeacherResponseType.NONE


@pytest.mark.asyncio
async def test_respond_to_missing_suggestion_is_not_found(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/coaching/does-not-exist/respond", json={"response": "acted"}
    )
    assert res.status_code == 404
