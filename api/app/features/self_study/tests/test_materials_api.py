"""T-212 — material upload Instant Answer vs Add-to-Library + privacy."""

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
from app.features.files.profiles import STUDENT_MATERIAL, get_profile
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.self_study.models import IndependentStudentMaterial

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
    published: list[dict[str, Any]] = []

    async def _fake_publish(*, payload: dict[str, Any]) -> None:
        published.append(payload)

    monkeypatch.setattr(
        "app.features.self_study.materials.IndependentUserRepository",
        _FakeIndUserRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.materials.UserRepository",
        lambda session: None,
    )
    monkeypatch.setattr(
        "app.features.self_study.materials.publish_self_study_material_uploaded",
        _fake_publish,
    )

    session = AsyncMock()

    class _ListResult:
        def scalars(self) -> Any:
            return self

        def all(self) -> list[IndependentStudentMaterial]:
            return list(_Store.rows)

    async def _execute(_stmt: object) -> _ListResult:
        return _ListResult()

    async def _commit() -> None:
        return None

    async def _refresh(row: IndependentStudentMaterial) -> None:
        if not getattr(row, "id", None):
            row.id = f"mat-{len(_Store.rows)}"

    def _add(row: IndependentStudentMaterial) -> None:
        if not getattr(row, "id", None):
            row.id = f"mat-{len(_Store.rows) + 1}"
        _Store.rows.append(row)

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock(side_effect=_commit)
    session.refresh = AsyncMock(side_effect=_refresh)
    session.add = _add
    session.get = AsyncMock(return_value=None)

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
        ac.session = session  # type: ignore[attr-defined]
        yield ac


def test_student_material_profile_registered() -> None:
    profile = get_profile("student_material")
    assert profile.name == STUDENT_MATERIAL.name
    assert "application/pdf" in profile.allowed_mime_types
    assert "image/jpeg" in profile.allowed_mime_types
    assert profile.strip_exif is True


@pytest.mark.asyncio
async def test_typed_instant_answer_not_persisted(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/self-study/me/materials/typed",
        json={
            "text": "What is Newton's second law?",
            "title": "Q",
            "disposition": "instant_answer",
        },
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["disposition"] == "instant_answer"
    assert body["material"] is None
    assert body["instant_answer_text"]
    assert body["event_emitted"] is True
    assert _Store.rows == []
    published = client.published  # type: ignore[attr-defined]
    assert published[0]["persisted_to_library"] is False
    assert published[0]["mode"] == "self_study"


@pytest.mark.asyncio
async def test_typed_add_to_library_persists(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/self-study/me/materials/typed",
        json={
            "text": "Chapter 5 notes",
            "title": "My notes",
            "disposition": "add_to_library",
        },
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["disposition"] == "add_to_library"
    assert body["material"]["added_to_library"] is True
    assert body["material"]["source_type"] == "typed"
    assert len(_Store.rows) == 1
    published = client.published  # type: ignore[attr-defined]
    assert published[0]["persisted_to_library"] is True


@pytest.mark.asyncio
async def test_list_library_own_only(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/self-study/me/materials/typed",
        json={
            "text": "Keep me",
            "title": "Lib",
            "disposition": "add_to_library",
        },
    )
    res = await client.get("/api/v1/self-study/me/materials")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Lib"
