"""API contract tests for independent private pool — T-074."""

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
from app.features.library.independent_personal_schemas import (
    IndependentPersonalContentRead,
    IndependentPersonalListResponse,
    IndependentPersonalUploadResponse,
)


class _FakeIndependentPersonalService:
    def __init__(self, session: Any) -> None:
        pass

    async def upload(self, **kwargs: Any) -> IndependentPersonalUploadResponse:
        item = IndependentPersonalContentRead(
            id="content-1",
            user_id="user-1",
            content_type="reference",
            title=str(kwargs["meta"].title),
            file_key="independent-personal/user-1/file.pdf",
            file_sha256="a" * 64,
            status="pending",
            structured_parsing_status="not_applicable",
            vector_collection="independent_personal_user-1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return IndependentPersonalUploadResponse(item=item, storage_deduplicated=False)

    async def list_items(
        self, claims: dict[str, object], **kwargs: Any
    ) -> IndependentPersonalListResponse:
        return IndependentPersonalListResponse(items=[], total=0)


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.library.independent_personal_router.IndependentPersonalContentService",
        _FakeIndependentPersonalService,
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
async def test_independent_upload_endpoint_accepts_pdf() -> None:
    pdf_bytes = b"%PDF-1.4\nsample"
    async with _build_client(
        {"sub": "auth-1", "role": "independent_teacher", "tenant_type": "independent"}
    ) as client:
        resp = await client.post(
            "/api/v1/independent/personal-content/?title=My%20Notes&content_type=reference",
            files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
        )
    assert resp.status_code == 202
    assert resp.json()["data"]["item"]["status"] == "pending"
