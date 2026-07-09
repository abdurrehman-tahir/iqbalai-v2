"""API contract tests for Academic Session endpoints — T-042."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.academic_sessions.models import AcademicSession


class _FakeSessionRepo:
    store: dict[str, AcademicSession] = {}
    school_active_label: dict[str, str | None] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school(self, school_id: str) -> list[AcademicSession]:
        return [s for s in self.store.values() if s.school_id == school_id and s.deleted_at is None]

    async def get_by_id(self, id: str) -> AcademicSession | None:
        return self.store.get(id)

    async def get_by_label(self, school_id: str, label: str) -> AcademicSession | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.school_id == school_id and s.label == label and s.deleted_at is None
            ),
            None,
        )

    async def get_active(self, school_id: str) -> AcademicSession | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.school_id == school_id and s.is_active and s.deleted_at is None
            ),
            None,
        )

    async def create(self, session_row: AcademicSession) -> AcademicSession:
        now = datetime.now(timezone.utc)
        session_row.created_at = now
        session_row.updated_at = now
        self.store[session_row.id] = session_row
        return session_row

    async def deactivate_all(self, school_id: str) -> None:
        for s in self.store.values():
            if s.school_id == school_id and s.is_active:
                s.is_active = False

    async def set_active(
        self, session_row: AcademicSession, school_id: str, label: str
    ) -> AcademicSession:
        await self.deactivate_all(school_id)
        session_row.is_active = True
        self.school_active_label[school_id] = label
        return session_row

    async def get_school_active_label(self, school_id: str) -> str | None:
        return self.school_active_label.get(school_id)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSessionRepo.store = {}
    _FakeSessionRepo.school_active_label = {}
    monkeypatch.setattr(
        "app.features.academic_sessions.service.AcademicSessionRepository", _FakeSessionRepo
    )
    monkeypatch.setattr("app.features.academic_sessions.service.audit", AsyncMock())


def _build_client(role: str = "coordinator", school_id: str = "school-1") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "user-1", "role": role, "school_id": school_id}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_list_empty_returns_no_sessions() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/academic-sessions/")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_create_session_returns_201() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/academic-sessions/",
            json={"label": "2025-2026", "set_active": True},
        )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["label"] == "2025-2026"
    assert data["is_active"] is True
    assert data["school_id"] == "school-1"


async def test_duplicate_label_same_school_returns_409() -> None:
    async with _build_client() as client:
        first = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": False}
        )
        assert first.status_code == 201
        dup = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": False}
        )
    assert dup.status_code == 409


async def test_only_one_active_session_per_school() -> None:
    async with _build_client() as client:
        s1 = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2024-2025", "set_active": True}
        )
        assert s1.status_code == 201
        s2 = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": True}
        )
        assert s2.status_code == 201
        listing = await client.get("/api/v1/academic-sessions/")
    active = [r for r in listing.json()["data"] if r["is_active"]]
    assert len(active) == 1
    assert active[0]["label"] == "2025-2026"


async def test_activate_session_deactivates_prior() -> None:
    async with _build_client() as client:
        s1 = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2024-2025", "set_active": True}
        )
        s2 = await client.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": False}
        )
        activate = await client.post(
            f"/api/v1/academic-sessions/{s2.json()['data']['id']}/activate"
        )
    assert activate.status_code == 200
    assert activate.json()["data"]["is_active"] is True
    get_s1 = _FakeSessionRepo.store[s1.json()["data"]["id"]]
    assert get_s1.is_active is False


async def test_same_label_different_school_allowed() -> None:
    async with _build_client(school_id="school-1") as client1:
        r1 = await client1.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": False}
        )
        assert r1.status_code == 201
    async with _build_client(school_id="school-2") as client2:
        r2 = await client2.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": False}
        )
    assert r2.status_code == 201


async def test_get_active_returns_label() -> None:
    async with _build_client() as client:
        await client.post(
            "/api/v1/academic-sessions/", json={"label": "2025-2026", "set_active": True}
        )
        resp = await client.get("/api/v1/academic-sessions/active")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["label"] == "2025-2026"
    assert data["session"]["label"] == "2025-2026"


async def test_teacher_forbidden() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.get("/api/v1/academic-sessions/")
    assert resp.status_code == 403
