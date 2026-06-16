"""API contract tests for school library soft-delete — T-064."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError, setup_exception_handlers
from app.features.library.school_library_schemas import SchoolLibraryItemRead
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
)


class _FakeSchoolLibraryService:
    def __init__(self, session: Any) -> None:
        pass

    async def soft_delete_item(self, item_id: str, authentik_id: str) -> SchoolLibraryItemRead:
        if item_id == "missing":
            raise NotFoundError("Library item not found")
        if item_id == "forbidden":
            raise PermissionDeniedError("You can only delete library items you uploaded")
        return SchoolLibraryItemRead(
            id=item_id,
            school_id="school-1",
            title="Physics Grade 9",
            content_type=LibraryContentType.CURRICULUM.value,
            language="en",
            subject_id="subj-1",
            grade_level_ordinal=9,
            storage_key="school-library/school-1/curriculum.pdf",
            sha256="a" * 64,
            ingestion_status=LibraryIngestionStatus.AVAILABLE.value,
            topic_tree_jsonb=None,
            created_by="teacher-1",
            visibility=LibraryVisibility.SCHOOL_PUBLIC.value,
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
async def test_delete_item_returns_soft_deleted_item() -> None:
    async with _build_client() as client:
        resp = await client.delete("/api/v1/school/library/item-curriculum-1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "item-curriculum-1"
    assert data["title"] == "Physics Grade 9"


@pytest.mark.asyncio
async def test_delete_item_not_found() -> None:
    async with _build_client() as client:
        resp = await client.delete("/api/v1/school/library/missing")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_forbidden() -> None:
    async with _build_client() as client:
        resp = await client.delete("/api/v1/school/library/forbidden")
    assert resp.status_code == 403
