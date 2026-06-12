"""API contract tests for Subject endpoints — T-041.

Covers the demo-script acceptance: empty state, create (201), duplicate (409),
edit-language persistence, archive (status flip + hidden from default list),
school-scoped uniqueness (a different school independently creates the same name),
plus the role gate (Teacher forbidden) and cross-school isolation (404).
"""

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
from app.features.subjects.models import Subject, SubjectStatus


class _FakeSubjectRepo:
    """In-memory stand-in for SubjectRepository, scoped by school like the real one."""

    store: dict[str, Subject] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school(self, school_id: str, include_archived: bool = False) -> list[Subject]:
        rows = [s for s in self.store.values() if s.school_id == school_id and s.deleted_at is None]
        if not include_archived:
            rows = [s for s in rows if s.status == SubjectStatus.ACTIVE]
        return rows

    async def get_by_id(self, id: str) -> Subject | None:
        return self.store.get(id)

    async def get_active_by_name(self, school_id: str, name: str) -> Subject | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.school_id == school_id and s.name == name and s.deleted_at is None
            ),
            None,
        )

    async def create(self, subject: Subject) -> Subject:
        now = datetime.now(timezone.utc)
        subject.created_at = now
        subject.updated_at = now
        self.store[subject.id] = subject
        return subject

    async def update(self, subject: Subject) -> Subject:
        self.store[subject.id] = subject
        return subject

    async def soft_delete(self, subject: Subject) -> None:
        subject.deleted_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSubjectRepo.store = {}
    monkeypatch.setattr("app.features.subjects.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.subjects.service.audit", AsyncMock())


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


async def test_list_empty_returns_no_subjects() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/subjects/")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_create_subject_returns_201() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Physics"
    assert data["language"] == "en"
    assert data["status"] == "active"
    assert data["school_id"] == "school-1"


async def test_duplicate_name_same_school_returns_409() -> None:
    async with _build_client() as client:
        first = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
        assert first.status_code == 201
        dup = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "ur"})
    assert dup.status_code == 409


async def test_edit_language_persists() -> None:
    async with _build_client() as client:
        created = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
        subject_id = created.json()["data"]["id"]
        resp = await client.put(f"/api/v1/subjects/{subject_id}", json={"language": "ur"})
    assert resp.status_code == 200
    assert resp.json()["data"]["language"] == "ur"


async def test_archive_hides_subject_from_default_list() -> None:
    async with _build_client() as client:
        created = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
        subject_id = created.json()["data"]["id"]

        archived = await client.post(f"/api/v1/subjects/{subject_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["data"]["status"] == "archived"

        default_list = await client.get("/api/v1/subjects/")
        assert default_list.json()["data"] == []

        with_archived = await client.get("/api/v1/subjects/?include_archived=true")
    assert len(with_archived.json()["data"]) == 1


async def test_school_scoped_uniqueness_allows_same_name_in_other_school() -> None:
    """Acceptance #6: a different school can independently create its own 'Physics'."""
    async with _build_client(school_id="school-1") as client_a:
        a = await client_a.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
    assert a.status_code == 201

    async with _build_client(school_id="school-2") as client_b:
        b = await client_b.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
    assert b.status_code == 201
    assert b.json()["data"]["school_id"] == "school-2"


async def test_cross_school_get_returns_404() -> None:
    other = Subject(id="subj-x", school_id="school-other", name="Chemistry", language="en")
    other.created_at = datetime.now(timezone.utc)
    other.updated_at = other.created_at
    _FakeSubjectRepo.store["subj-x"] = other

    async with _build_client(school_id="school-1") as client:
        resp = await client.get("/api/v1/subjects/subj-x")
    assert resp.status_code == 404


async def test_teacher_forbidden() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.post("/api/v1/subjects/", json={"name": "Physics", "language": "en"})
    assert resp.status_code == 403
