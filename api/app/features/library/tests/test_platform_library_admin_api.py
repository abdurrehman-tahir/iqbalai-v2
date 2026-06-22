"""API contract tests for platform admin library upload guards — T-072."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers


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
async def test_teacher_cannot_upload_to_admin_library() -> None:
    pdf_bytes = b"%PDF-1.4\nsample"
    async with _build_client(
        {"sub": "teacher-1", "role": "teacher", "school_id": "school-1"}
    ) as client:
        resp = await client.post(
            "/api/v1/admin/library/?title=Physics&content_type=reference",
            files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_independent_user_cannot_upload_to_admin_library() -> None:
    pdf_bytes = b"%PDF-1.4\nsample"
    async with _build_client(
        {"sub": "ind-1", "role": "independent_teacher", "tenant_type": "independent"}
    ) as client:
        resp = await client.post(
            "/api/v1/admin/library/?title=Physics&content_type=reference",
            files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_independent_user_cannot_delete_admin_library_item() -> None:
    async with _build_client(
        {"sub": "ind-1", "role": "independent_teacher", "tenant_type": "independent"}
    ) as client:
        resp = await client.delete("/api/v1/admin/library/book-1")
    assert resp.status_code == 403
