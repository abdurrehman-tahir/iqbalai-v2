"""API contract tests for coordinator bulk import — T-037."""

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
from app.features.bulk_imports.models import BulkImport, BulkImportStatus
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.users.models import User, UserRole


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return self.users.get(authentik_id)

    async def get_by_email(self, email: str) -> User | None:
        return None


class _FakeBulkImportRepo:
    store: dict[str, BulkImport] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def save(self, job: BulkImport) -> BulkImport:
        now = datetime.now(timezone.utc)
        if not job.id:
            job.id = "job-generated"
        job.created_at = now
        job.updated_at = now
        self.store[job.id] = job
        return job

    async def get_by_id_for_school(self, import_id: str, school_id: str) -> BulkImport | None:
        job = self.store.get(import_id)
        if job is None or job.school_id != school_id:
            return None
        return job


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeBulkImportRepo.store = {}
    _FakeUserRepo.users = {
        "coord-auth": User(
            id="coord-1",
            authentik_id="coord-auth",
            email="coord@test.com",
            display_name="Coord",
            role=UserRole.COORDINATOR,
            school_id="school-1",
            scoped_ids="Grade 9,Grade 10",
        ),
    }
    monkeypatch.setattr("app.features.bulk_imports.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.bulk_imports.service.BulkImportRepository", _FakeBulkImportRepo)
    monkeypatch.setattr("app.features.bulk_imports.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.bulk_imports.service.run_upload_pipeline",
        AsyncMock(
            return_value=UploadInitiated(
                upload_id="upload-1",
                status=UploadStatus.READY,
                status_url="/api/v1/uploads/upload-1",
            )
        ),
    )


def _build_client(role: str = "coordinator") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "coord-auth",
        "role": role,
        "school_id": "school-1",
    }

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_coordinator_can_upload_csv_dry_run() -> None:
    csv_content = (
        "name,email,grade\n"
        "Alice,alice@test.com,Grade 9\n"
        "Bob,bad@test.com,Grade 11\n"
    )
    async with _build_client() as client:
        res = await client.post(
            "/api/v1/coordinator/bulk-imports/",
            files={"file": ("students.csv", csv_content.encode(), "text/csv")},
        )

    assert res.status_code == 201
    body = res.json()
    assert body["data"]["total_rows"] == 2
    assert body["data"]["success_rows"] == 1
    assert body["data"]["failed_rows"] == 1
    assert body["data"]["status"] == "dry_run_complete"


@pytest.mark.asyncio
async def test_teacher_cannot_upload_bulk_import() -> None:
    csv_content = "name,email,grade\nAlice,alice@test.com,Grade 9\n"
    async with _build_client(role="teacher") as client:
        res = await client.post(
            "/api/v1/coordinator/bulk-imports/",
            files={"file": ("students.csv", csv_content.encode(), "text/csv")},
        )

    assert res.status_code == 403
