"""API contract tests for school library list — T-060."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.library.school_library_schemas import (
    SchoolLibraryItemRead,
    SchoolLibraryListResponse,
)
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
)


class _FakeSchoolLibraryService:
    def __init__(self, session: Any) -> None:
        pass

    async def list_items(self, authentik_id: str, **kwargs: Any) -> SchoolLibraryListResponse:
        return SchoolLibraryListResponse(
            items=[
                SchoolLibraryItemRead(
                    id="item-public",
                    school_id="school-1",
                    title="Punjab Physics Grade 9",
                    content_type=LibraryContentType.CURRICULUM.value,
                    language="en",
                    subject_id="subj-1",
                    grade_level_ordinal=9,
                    storage_key="school-library/school-1/curriculum.pdf",
                    sha256="a" * 64,
                    ingestion_status=LibraryIngestionStatus.AVAILABLE.value,
                    topic_tree_jsonb=None,
                    created_by="coord-1",
                    visibility=LibraryVisibility.SCHOOL_PUBLIC.value,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                SchoolLibraryItemRead(
                    id="item-private",
                    school_id="school-1",
                    title="My Notes",
                    content_type=LibraryContentType.REFERENCE.value,
                    language="en",
                    subject_id=None,
                    grade_level_ordinal=None,
                    storage_key="school-library/school-1/notes.pdf",
                    sha256="b" * 64,
                    ingestion_status=LibraryIngestionStatus.AVAILABLE.value,
                    topic_tree_jsonb=None,
                    created_by="teacher-1",
                    visibility=LibraryVisibility.PRIVATE.value,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
            ],
            total=2,
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
async def test_list_items_returns_visible_items() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/library/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["ingestion_status"] == "available"


@pytest.mark.asyncio
async def test_list_items_accepts_filters() -> None:
    async with _build_client() as client:
        resp = await client.get(
            "/api/v1/school/library/",
            params={
                "subject_id": "subj-1",
                "grade_level_ordinal": 9,
                "language": "en",
                "content_type": "curriculum",
                "title": "Physics",
            },
        )
    assert resp.status_code == 200
