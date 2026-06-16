"""API contract tests for school library reference publish/selection — T-059."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PreconditionFailedError, setup_exception_handlers
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)


class _FakeSchoolLibraryService:
    def __init__(self, session: Any) -> None:
        pass

    async def publish_reference(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        if item_id == "missing":
            raise NotFoundError("Library item not found")
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
            ingestion_status=LibraryIngestionStatus.AVAILABLE,
            topic_tree_jsonb=None,
            created_by="teacher-1",
            visibility=LibraryVisibility.SCHOOL_PUBLIC,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def set_reference_visibility(
        self, item_id: str, visibility: str, authentik_id: str
    ) -> SchoolLibraryItem:
        if visibility == "private":
            raise PreconditionFailedError(
                "Once shared with the school, content cannot be made private. "
                "You can remove your selection but the content stays available to others."
            )
        return await self.publish_reference(item_id, authentik_id)

    async def remove_selection(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        if item_id == "missing":
            raise NotFoundError("Library selection not found")
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
            ingestion_status=LibraryIngestionStatus.AVAILABLE,
            topic_tree_jsonb=None,
            created_by="teacher-1",
            visibility=LibraryVisibility.SCHOOL_PUBLIC,
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
async def test_publish_reference_returns_public_item() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/school/library/ref-item-1/publish")
    assert resp.status_code == 200
    assert resp.json()["data"]["visibility"] == "school_public"


@pytest.mark.asyncio
async def test_set_visibility_private_blocked() -> None:
    async with _build_client() as client:
        resp = await client.patch(
            "/api/v1/school/library/ref-item-1/visibility",
            params={"visibility": "private"},
        )
    assert resp.status_code == 412
    assert "cannot be made private" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_remove_selection_returns_item() -> None:
    async with _build_client() as client:
        resp = await client.delete("/api/v1/school/library/ref-item-1/selection")
    assert resp.status_code == 200
    assert resp.json()["data"]["visibility"] == "school_public"


@pytest.mark.asyncio
async def test_remove_selection_not_found() -> None:
    async with _build_client() as client:
        resp = await client.delete("/api/v1/school/library/missing/selection")
    assert resp.status_code == 404
