"""API contract tests for school admin audit log — T-039."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.audit.models import AuditLogEntry


class _FakeAuditRepo:
    entries: list[AuditLogEntry] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_recent(
        self,
        school_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        rows = self.entries
        if school_id is not None:
            rows = [e for e in rows if e.school_id == school_id]
        rows = sorted(rows, key=lambda e: e.created_at, reverse=True)
        return rows[offset : offset + limit]


@pytest.fixture(autouse=True)
def _patch_audit_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    _FakeAuditRepo.entries = [
        AuditLogEntry(
            id="a1",
            action="user.invite_sent",
            actor_id="sa-1",
            actor_role="school_admin",
            target_type="user_invite",
            target_id="inv-1",
            school_id="school-1",
            created_at=now,
        ),
        AuditLogEntry(
            id="a2",
            action="user.suspended",
            actor_id="sa-1",
            actor_role="school_admin",
            target_type="user",
            target_id="u-1",
            school_id="school-1",
            created_at=now,
        ),
        AuditLogEntry(
            id="a3",
            action="user.invite_sent",
            actor_id="sa-2",
            actor_role="school_admin",
            target_type="user_invite",
            target_id="inv-2",
            school_id="school-2",
            created_at=now,
        ),
    ]
    monkeypatch.setattr("app.features.audit.school_admin_router.AuditRepository", _FakeAuditRepo)


def _build_client(
    role: str = "school_admin",
    school_id: str | None = "school-1",
) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        data: dict[str, object] = {"sub": "sa-1", "role": role}
        if school_id is not None:
            data["school_id"] = school_id
        return data

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_school_admin_sees_own_school_audit_entries() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/admin/audit-log/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert all(item["school_id"] == "school-1" for item in body["items"])


async def test_school_admin_cannot_see_other_school_via_jwt_scope() -> None:
    async with _build_client(school_id="school-2") as client:
        resp = await client.get("/api/v1/school/admin/audit-log/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["school_id"] == "school-2"


async def test_teacher_cannot_access_school_audit_log() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.get("/api/v1/school/admin/audit-log/")
    assert resp.status_code == 403


async def test_platform_admin_audit_log_still_requires_platform_role() -> None:
    async with _build_client(role="school_admin") as client:
        resp = await client.get("/api/v1/admin/audit-log/")
    assert resp.status_code == 403
