"""API contract tests for school library upload — T-055."""

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
    SchoolLibraryUploadResponse,
)
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)


class _FakeSchoolLibraryService:
    last_upload: dict[str, Any] | None = None

    def __init__(self, session: Any) -> None:
        pass

    async def upload(self, **kwargs: Any) -> SchoolLibraryUploadResponse:
        _FakeSchoolLibraryService.last_upload = kwargs
        item = SchoolLibraryItem(
            id="item-1",
            school_id="school-1",
            title=str(kwargs["meta"].title),
            content_type=LibraryContentType.REFERENCE,
            language="en",
            subject_id=None,
            grade_level_ordinal=None,
            storage_key="school-library/school-1/file.pdf",
            sha256="a" * 64,
            ingestion_status=LibraryIngestionStatus.PENDING,
            created_by="teacher-1",
            visibility=LibraryVisibility.PRIVATE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return SchoolLibraryUploadResponse(
            item=SchoolLibraryItemRead.model_validate(item),
            storage_deduplicated=False,
            selection_created=True,
        )


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSchoolLibraryService.last_upload = None
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
async def test_upload_endpoint_accepts_pdf() -> None:
    pdf_bytes = b"%PDF-1.4\nsample"
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/school/library/?title=Physics%20Notes&content_type=reference",
            files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
        )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["item"]["ingestion_status"] == "pending"
    assert data["selection_created"] is True
    assert _FakeSchoolLibraryService.last_upload is not None
    assert _FakeSchoolLibraryService.last_upload["filename"] == "notes.pdf"
