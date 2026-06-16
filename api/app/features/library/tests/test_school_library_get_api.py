"""API contract tests for school library GET item — T-058."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, setup_exception_handlers
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)


class _FakeSchoolLibraryService:
    def __init__(self, session: Any) -> None:
        pass

    async def get_item(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        if item_id == "missing":
            raise NotFoundError("Library item not found")
        return SchoolLibraryItem(
            id=item_id,
            school_id="school-1",
            title="Punjab Physics Grade 9",
            content_type=LibraryContentType.CURRICULUM,
            language="en",
            subject_id="subj-1",
            grade_level_ordinal=9,
            storage_key="school-library/school-1/curriculum.pdf",
            sha256="b" * 64,
            ingestion_status=LibraryIngestionStatus.AVAILABLE,
            topic_tree_jsonb={
                "chapters": [
                    {
                        "title": "Mechanics",
                        "sections": [{"title": "Motion", "sub_topics": ["Speed"]}],
                    }
                ],
                "parse_degraded": False,
            },
            created_by="coord-1",
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
        "sub": "coord-1",
        "role": "coordinator",
        "school_id": "school-1",
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_item_returns_topic_tree() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/library/item-curriculum-1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["content_type"] == "curriculum"
    assert data["visibility"] == "school_public"
    assert data["topic_tree_jsonb"]["chapters"][0]["title"] == "Mechanics"


@pytest.mark.asyncio
async def test_get_item_not_found() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/library/missing")
    assert resp.status_code == 404
