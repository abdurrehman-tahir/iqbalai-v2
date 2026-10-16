"""T-211 — daily goal API contract + achievement check."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
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
from app.features.self_study.models import IndependentStudentGoal

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


class _GoalStore:
    row: IndependentStudentGoal | None = None


class _FakeResult:
    def __init__(self, row: IndependentStudentGoal | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> IndependentStudentGoal | None:
        return self._row


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    _GoalStore.row = None
    published: list[tuple[str, dict[str, Any]]] = []

    async def _fake_publish_set(*, payload: dict[str, Any]) -> None:
        published.append(("set", payload))

    async def _fake_publish_achieved(*, payload: dict[str, Any]) -> None:
        published.append(("achieved", payload))

    monkeypatch.setattr(
        "app.features.self_study.goals.IndependentUserRepository",
        _FakeIndUserRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.goals.UserRepository",
        lambda session: None,
    )
    monkeypatch.setattr(
        "app.features.self_study.goals.today_karachi",
        lambda: date(2026, 10, 15),
    )
    monkeypatch.setattr(
        "app.features.self_study.goals.publish_self_study_goal_set",
        _fake_publish_set,
    )
    monkeypatch.setattr(
        "app.features.self_study.goals.publish_self_study_goal_achieved",
        _fake_publish_achieved,
    )

    session = AsyncMock()

    async def _execute(stmt: object) -> _FakeResult:
        return _FakeResult(_GoalStore.row)

    async def _commit() -> None:
        return None

    async def _refresh(row: IndependentStudentGoal) -> None:
        if not row.id:
            row.id = "goal-1"

    def _add(row: IndependentStudentGoal) -> None:
        if not getattr(row, "id", None):
            row.id = "goal-1"
        _GoalStore.row = row

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock(side_effect=_commit)
    session.refresh = AsyncMock(side_effect=_refresh)
    session.add = _add

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
        ac.published = published  # type: ignore[attr-defined]
        yield ac


@pytest.mark.asyncio
async def test_get_goal_empty(client: AsyncClient) -> None:
    res = await client.get("/api/v1/self-study/me/goal")
    assert res.status_code == 200
    assert res.json()["data"]["goal"] is None


@pytest.mark.asyncio
async def test_set_goal_publishes_event(client: AsyncClient) -> None:
    res = await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Master chapter 5 kinematics", "confirm_replace": False},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["goal_text"] == "Master chapter 5 kinematics"
    assert body["tenant_type"] == "independent"
    assert body["achievement_check_pending"] is True
    published = client.published  # type: ignore[attr-defined]
    assert len(published) == 1
    assert published[0][0] == "set"
    assert published[0][1]["mode"] == "self_study"


@pytest.mark.asyncio
async def test_replace_requires_confirm(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "First goal", "confirm_replace": False},
    )
    res = await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Second goal", "confirm_replace": False},
    )
    assert res.status_code == 409
    res_ok = await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Second goal", "confirm_replace": True},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["data"]["goal_text"] == "Second goal"


@pytest.mark.asyncio
async def test_achievement_skippable_after_five_minutes(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Finish practice set", "confirm_replace": False},
    )
    res = await client.post(
        "/api/v1/self-study/me/goal/achievement",
        json={"skip": True, "session_duration_seconds": 301},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["achievement_check_pending"] is False
    published = client.published  # type: ignore[attr-defined]
    assert not any(p[0] == "achieved" for p in published)


@pytest.mark.asyncio
async def test_achievement_yes_emits_event(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Finish practice set", "confirm_replace": False},
    )
    res = await client.post(
        "/api/v1/self-study/me/goal/achievement",
        json={"achieved": True, "skip": False, "session_duration_seconds": 400},
    )
    assert res.status_code == 200
    assert res.json()["data"]["achieved"] is True
    published = client.published  # type: ignore[attr-defined]
    assert any(p[0] == "achieved" for p in published)


@pytest.mark.asyncio
async def test_short_session_no_check_side_effect(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/self-study/me/goal",
        json={"goal_text": "Short session goal", "confirm_replace": False},
    )
    res = await client.post(
        "/api/v1/self-study/me/goal/achievement",
        json={"achieved": True, "skip": False, "session_duration_seconds": 60},
    )
    assert res.status_code == 200
    assert res.json()["data"]["achievement_check_pending"] is True
