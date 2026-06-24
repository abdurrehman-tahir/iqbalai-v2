"""API contract tests for school library retry ingestion — T-061."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ValidationError, setup_exception_handlers
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)


class _FakeSchoolLibraryService:
    def __init__(self, session: Any) -> None:
        pass

    async def retry_ingestion(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        if item_id == "available-item":
            raise ValidationError("This item is already available")
        return SchoolLibraryItem(
            id=item_id,
            school_id="school-1",
            title="Physics Notes",
            content_type=LibraryContentType.REFERENCE,
            language="en",
            subject_id=None,
            grade_level_ordinal=None,
            storage_key="school-library/school-1/notes.pdf",
            sha256="b" * 64,
            ingestion_status=LibraryIngestionStatus.PENDING,
            ingestion_error=None,
            topic_tree_jsonb=None,
            created_by="teacher-1",
            visibility=LibraryVisibility.PRIVATE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.library.school_library_router.SchoolLibraryService",
        _FakeSchoolLibraryService,
    )


def _build_client() -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "teacher-1",
        "role": "teacher",
        "school_id": "school-1",
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_retry_ingestion_resets_to_pending() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/school/library/failed-item/retry-ingestion")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ingestion_status"] == "pending"
    assert data["ingestion_error"] is None


@pytest.mark.asyncio
async def test_retry_ingestion_rejects_available_item() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/school/library/available-item/retry-ingestion")
    assert resp.status_code == 422
