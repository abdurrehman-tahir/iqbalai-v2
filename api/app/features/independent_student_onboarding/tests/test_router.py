"""API contract test for GET /independent/students/me/exam-frameworks — T-238.

The route was exempted in PUBLIC_PATHS since M-05 (0e9f6b5) — a `/me/` endpoint
cannot resolve a user without auth, so the exemption was an auth-bypass, not a
feature. It now requires `independent_student` like its onboarding siblings.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _empty_list(self: Any) -> list[Any]:
        return []

    monkeypatch.setattr(
        "app.features.independent_student_onboarding.service.IndependentStudentOnboardingService"
        ".list_exam_frameworks",
        _empty_list,
    )


def _build_client(claims: dict[str, object] | None) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    if claims is not None:
        app.dependency_overrides[get_current_user] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_exam_frameworks_requires_auth() -> None:
    async with _build_client(claims=None) as client:
        resp = await client.get("/api/v1/independent/students/me/exam-frameworks")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_exam_frameworks_returns_200_for_independent_student() -> None:
    async with _build_client(
        claims={"sub": "student-1", "role": "independent_student"}
    ) as client:
        resp = await client.get("/api/v1/independent/students/me/exam-frameworks")

    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_exam_frameworks_forbidden_for_wrong_role() -> None:
    async with _build_client(claims={"sub": "u-1", "role": "school_admin"}) as client:
        resp = await client.get("/api/v1/independent/students/me/exam-frameworks")

    assert resp.status_code == 403
