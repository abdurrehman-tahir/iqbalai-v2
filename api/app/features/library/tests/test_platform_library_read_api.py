"""API contract tests for platform library read access — T-073."""

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
from app.features.library.schemas import LibraryBookListResponse, LibraryBookRead


class _FakePlatformLibraryReadService:
    def __init__(self, session: Any) -> None:
        pass

    async def list_books(self, claims: dict[str, object], **kwargs: Any) -> LibraryBookListResponse:
        return LibraryBookListResponse(
            items=[
                LibraryBookRead(
                    id="book-1",
                    upload_id="upload-1",
                    title="Platform Physics",
                    content_type="reference",
                    subject_tag="physics",
                    grade_range_min=9,
                    grade_range_max=10,
                    language="en",
                    sha256="a" * 64,
                    status="available",
                    qdrant_collection="platform_chunks",
                    chunk_count=12,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    deleted_at=None,
                )
            ],
            total=1,
        )

    async def get_book(self, book_id: str, claims: dict[str, object]) -> LibraryBookRead:
        return LibraryBookRead(
            id=book_id,
            upload_id="upload-1",
            title="Platform Physics",
            content_type="reference",
            subject_tag="physics",
            grade_range_min=9,
            grade_range_max=10,
            language="en",
            sha256="a" * 64,
            status="available",
            qdrant_collection="platform_chunks",
            chunk_count=12,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.library.platform_library_router.PlatformLibraryReadService",
        _FakePlatformLibraryReadService,
    )


def _build_client(claims: dict[str, object]) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_independent_teacher_can_list_platform_library() -> None:
    async with _build_client(
        {"sub": "ind-1", "role": "independent_teacher", "tenant_type": "independent"}
    ) as client:
        resp = await client.get("/api/v1/platform/library/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["status"] == "available"


@pytest.mark.asyncio
async def test_school_student_can_list_platform_library() -> None:
    async with _build_client(
        {"sub": "stu-1", "role": "student", "tenant_type": "school", "school_id": "school-1"}
    ) as client:
        resp = await client.get("/api/v1/platform/library/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_platform_library_book() -> None:
    async with _build_client(
        {"sub": "ind-2", "role": "independent_student", "tenant_type": "independent"}
    ) as client:
        resp = await client.get("/api/v1/platform/library/book-1")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "book-1"
