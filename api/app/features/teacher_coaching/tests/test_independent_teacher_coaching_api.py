"""T-138 — Teaching Innovation Record API (independent tenant, brief mirror)."""

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
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.teacher_coaching.models import IndependentTeacherAiMemory, TeacherResponseType

TEACHER = IndependentUser(
    id="ind-teacher-1",
    authentik_id="auth-ind-teacher",
    email="ind-teacher@example.com",
    display_name="Independent Teacher",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
)

PENDING = IndependentTeacherAiMemory(
    teacher_user_id="ind-teacher-1",
    category="quality_dimension",
    weakness_type="depth",
    frequency=1,
    last_suggestion="Add one worked example before moving on.",
    teacher_response=TeacherResponseType.NONE,
    created_at=datetime.now(timezone.utc),
)
PENDING.updated_at = datetime.now(timezone.utc)


class _FakeUserRepo:
    store: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeMemoryRepo:
    store: dict[str, IndependentTeacherAiMemory] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, memory_id: str) -> IndependentTeacherAiMemory | None:
        return self.store.get(memory_id)

    async def list_pending_for_teacher(
        self, teacher_user_id: str
    ) -> list[IndependentTeacherAiMemory]:
        return [
            r
            for r in self.store.values()
            if r.teacher_user_id == teacher_user_id
            and r.teacher_response == TeacherResponseType.NONE
        ]

    async def update(self, memory: IndependentTeacherAiMemory) -> IndependentTeacherAiMemory:
        return memory


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    PENDING.teacher_response = TeacherResponseType.NONE
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeMemoryRepo.store = {PENDING.id: PENDING}

    monkeypatch.setattr(
        "app.features.teacher_coaching.service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.IndependentTeacherAiMemoryRepository",
        _FakeMemoryRepo,
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-ind-teacher", "role": "independent_teacher", "user_id": "ind-teacher-1"}


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_and_respond_roundtrip(client: AsyncClient) -> None:
    list_res = await client.get("/api/v1/independent/teachers/me/coaching")
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) == 1

    respond_res = await client.post(
        f"/api/v1/independent/teachers/me/coaching/{PENDING.id}/respond",
        json={"response": "ignored"},
    )
    assert respond_res.status_code == 200
    assert PENDING.teacher_response == TeacherResponseType.IGNORED
