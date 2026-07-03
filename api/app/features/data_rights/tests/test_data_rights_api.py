"""Data rights API tests — T-084."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.data_rights.models import (
    DataRightsRequest,
    DataRightsRequestStatus,
    DataRightsRequestType,
)
from app.features.data_rights.tests.test_data_rights_service import (
    CLAIMS,
    STUDENT,
    _FakeRequestRepo,
    _FakeStudentProfileRepo,
    _FakeUserRepo,
)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(application)

    async def _override_user() -> dict[str, str]:
        return CLAIMS

    async def _override_db() -> AsyncGenerator[AsyncMock, None]:
        session = AsyncMock()
        session.commit = AsyncMock()
        yield session

    application.dependency_overrides[get_current_user] = _override_user
    application.dependency_overrides[get_db] = _override_db
    return application


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRequestRepo.store = {}
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    _FakeStudentProfileRepo.store = {}

    monkeypatch.setattr(
        "app.features.data_rights.service.DataRightsRequestRepository", _FakeRequestRepo
    )
    monkeypatch.setattr("app.features.data_rights.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.data_rights.service.StudentProfileRepository", _FakeStudentProfileRepo
    )
    monkeypatch.setattr("app.features.data_rights.service.ParentProfileRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.ParentChildLinkRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.StudentEnrollmentRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.data_rights.service.notify_account_event", AsyncMock())
    monkeypatch.setattr(
        "app.features.data_rights.tasks.process_data_export.delay",
        MagicMock(),
    )


@pytest.mark.asyncio
async def test_student_request_export_returns_201(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/students/me/data-rights/export")

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["request_type"] == "export"
    assert body["status"] == "requested"


@pytest.mark.asyncio
async def test_student_request_deletion_returns_grace_period(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/students/me/data-rights/deletion",
            json={"confirm": True},
        )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["request_type"] == "deletion"
    assert body["status"] == "grace_period"
    assert body["deletion_scheduled_at"] is not None


@pytest.mark.asyncio
async def test_student_download_ready_export(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timedelta, timezone

    request = DataRightsRequest(
        id="export-1",
        user_id=STUDENT.id,
        request_type=DataRightsRequestType.EXPORT,
        status=DataRightsRequestStatus.READY,
        requested_at=datetime.now(timezone.utc),
        ready_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        file_key="exports/student-1/export-1.zip",
    )
    _FakeRequestRepo.store[request.id] = request

    monkeypatch.setattr(
        "app.features.data_rights.service.download_bytes",
        lambda bucket, key: b"PK\x03\x04fake-zip",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/students/me/data-rights/export/export-1/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.content.startswith(b"PK")
