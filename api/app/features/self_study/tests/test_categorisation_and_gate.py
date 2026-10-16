"""T-213 — book categorisation + prep-book hard gate."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.self_study.categorisation import PREP_BOOK_GATE_ERROR
from app.features.self_study.models import (
    IndependentStudentMaterial,
    MaterialBookType,
    MaterialSourceType,
)

IND_STUDENT = IndependentUser(
    id="ind-u1",
    authentik_id="auth-ind-1",
    email="i@example.com",
    display_name="Ind Student",
    role=IndependentUserRole.INDEPENDENT_STUDENT,
    status=IndependentUserAccountStatus.ACTIVE,
)


class _FakeIndUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return IND_STUDENT if authentik_id == "auth-ind-1" else None


class _Store:
    rows: list[IndependentStudentMaterial] = []


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    _Store.rows = []
    monkeypatch.setattr(
        "app.features.self_study.categorisation.IndependentUserRepository",
        _FakeIndUserRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.categorisation.UserRepository",
        lambda session: None,
    )
    monkeypatch.setattr(
        "app.features.self_study.plans.IndependentUserRepository",
        _FakeIndUserRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.plans.UserRepository",
        lambda session: None,
    )

    session = AsyncMock()

    class _Result:
        def __init__(self, row: Any = None, count: int = 0) -> None:
            self._row = row
            self._count = count

        def scalar_one_or_none(self) -> Any:
            return self._row

        def scalar_one(self) -> int:
            return self._count

    async def _execute(stmt: object) -> _Result:
        sql = str(stmt).lower()
        if "count" in sql:
            n = sum(
                1
                for r in _Store.rows
                if r.book_type == MaterialBookType.PREP_QUESTIONS and r.added_to_library
            )
            return _Result(count=n)
        mat_id = None
        for r in _Store.rows:
            mat_id = r  # last match fallback
        # Prefer exact id when only one row
        if len(_Store.rows) == 1:
            return _Result(row=_Store.rows[0])
        return _Result(row=mat_id)

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")

    async def _claims() -> dict[str, object]:
        return {
            "sub": "auth-ind-1",
            "role": "independent_student",
            "tenant_type": "independent",
        }

    async def _db() -> AsyncGenerator[Any, None]:
        yield session

    app.dependency_overrides[get_current_user] = _claims
    app.dependency_overrides[get_db] = _db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_gate_blocked_without_prep_book(client: AsyncClient) -> None:
    res = await client.get("/api/v1/self-study/me/plans/gate")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["allowed"] is False
    assert data["error_message"] == PREP_BOOK_GATE_ERROR


@pytest.mark.asyncio
async def test_categorise_prep_unlocks_gate(client: AsyncClient) -> None:
    mat = IndependentStudentMaterial(
        id="mat-1",
        student_user_id=IND_STUDENT.id,
        title="Prep pack",
        source_type=MaterialSourceType.PDF,
        added_to_library=True,
        book_type=None,
    )
    _Store.rows.append(mat)

    res = await client.patch(
        "/api/v1/self-study/me/materials/mat-1/book-type",
        json={"book_type": "prep_questions"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["book_type"] == "prep_questions"
    assert mat.book_type == MaterialBookType.PREP_QUESTIONS

    gate = await client.get("/api/v1/self-study/me/plans/gate")
    assert gate.json()["data"]["allowed"] is True
    assert gate.json()["data"]["error_message"] is None


@pytest.mark.asyncio
async def test_plan_conversation_hard_blocked(client: AsyncClient) -> None:
    res = await client.get("/api/v1/self-study/me/plans/conversation")
    assert res.status_code == 422
    body = res.json()
    msg = body.get("error", {}).get("message") or body.get("message") or str(body)
    assert PREP_BOOK_GATE_ERROR in msg
