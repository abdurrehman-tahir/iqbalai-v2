"""API contract tests for parent-child links — T-081."""

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
from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus
from app.features.parent_signup.models import ParentProfile
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeUserRepo:
    store: dict[str, User] = {}
    by_email: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        return self.store.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self.by_email.get(email.lower())


class _FakeParentProfileRepo:
    store: dict[str, ParentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> ParentProfile | None:
        return self.store.get(user_id)

    async def update(self, profile: ParentProfile) -> ParentProfile:
        self.store[profile.user_id] = profile
        return profile


class _FakeLinkRepo:
    store: dict[str, ParentChildLink] = {}
    by_pair: dict[tuple[str, str], ParentChildLink] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, link_id: str) -> ParentChildLink | None:
        return self.store.get(link_id)

    async def get_by_parent_and_student(
        self, *, parent_user_id: str, student_user_id: str
    ) -> ParentChildLink | None:
        return self.by_pair.get((parent_user_id, student_user_id))

    async def list_for_parent(self, parent_user_id: str) -> list[ParentChildLink]:
        return [link for link in self.store.values() if link.parent_user_id == parent_user_id]

    async def list_pending_for_student(self, student_user_id: str) -> list[ParentChildLink]:
        return [
            link
            for link in self.store.values()
            if link.student_user_id == student_user_id
            and link.status == ParentChildLinkStatus.PENDING
        ]

    async def list_approved_for_parent(self, parent_user_id: str) -> list[ParentChildLink]:
        return [
            link
            for link in self.store.values()
            if link.parent_user_id == parent_user_id
            and link.status == ParentChildLinkStatus.APPROVED
        ]

    async def create(self, link: ParentChildLink) -> ParentChildLink:
        now = datetime.now(timezone.utc)
        link.created_at = now
        link.updated_at = now
        self.store[link.id] = link
        self.by_pair[(link.parent_user_id, link.student_user_id)] = link
        return link

    async def update(self, link: ParentChildLink) -> ParentChildLink:
        self.store[link.id] = link
        self.by_pair[(link.parent_user_id, link.student_user_id)] = link
        return link


class _FakeIndependentUserRepo:
    by_email: dict[str, object] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> object | None:
        return self.by_email.get(email.lower())


PARENT = User(
    id="parent-1",
    authentik_id="auth-parent",
    email="parent@example.com",
    display_name="Parent One",
    role=UserRole.PARENT,
    status=UserAccountStatus.ACTIVE,
)

STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

PARENT_PROFILE = ParentProfile(
    user_id=PARENT.id,
    name=PARENT.display_name,
    language_preference="en",
    is_email_verified=True,
    unlinked_since=datetime.now(timezone.utc),
)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {PARENT.id: PARENT, STUDENT.id: STUDENT}
    _FakeUserRepo.by_email = {
        PARENT.email: PARENT,
        STUDENT.email: STUDENT,
    }
    _FakeParentProfileRepo.store = {PARENT.id: PARENT_PROFILE}
    _FakeLinkRepo.store = {}
    _FakeLinkRepo.by_pair = {}
    _FakeIndependentUserRepo.by_email = {}

    monkeypatch.setattr(
        "app.features.parent_child_links.service.UserRepository",
        _FakeUserRepo,
    )
    monkeypatch.setattr(
        "app.features.parent_child_links.service.ParentProfileRepository",
        _FakeParentProfileRepo,
    )
    monkeypatch.setattr(
        "app.features.parent_child_links.service.ParentChildLinkRepository",
        _FakeLinkRepo,
    )
    monkeypatch.setattr(
        "app.features.parent_child_links.service.IndependentUserRepository",
        _FakeIndependentUserRepo,
    )
    monkeypatch.setattr("app.features.parent_child_links.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.parent_child_links.service.notify_connections_event",
        AsyncMock(),
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None  # type: ignore[misc]


def _build_client(claims: dict[str, object]) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _parent_claims() -> dict[str, object]:
    return {
        "sub": PARENT.authentik_id,
        "user_id": PARENT.id,
        "role": PARENT.role.value,
        "email": PARENT.email,
        "tenant_type": "school",
    }


def _student_claims() -> dict[str, object]:
    return {
        "sub": STUDENT.authentik_id,
        "user_id": STUDENT.id,
        "role": STUDENT.role.value,
        "email": STUDENT.email,
        "tenant_type": "school",
        "school_id": STUDENT.school_id,
    }


@pytest.mark.asyncio
async def test_parent_creates_link_request_pending() -> None:
    async with _build_client(_parent_claims()) as client:
        resp = await client.post(
            "/api/v1/parents/me/link-requests",
            json={"student_email": STUDENT.email},
        )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["status"] == "pending"
    assert body["student_email"] == STUDENT.email
    assert len(_FakeLinkRepo.store) == 1


@pytest.mark.asyncio
async def test_link_request_unknown_email_returns_generic_error() -> None:
    async with _build_client(_parent_claims()) as client:
        resp = await client.post(
            "/api/v1/parents/me/link-requests",
            json={"student_email": "missing@example.com"},
        )
    assert resp.status_code == 422
    assert "Unable to send link request" in resp.json()["error"]["message"]
    assert len(_FakeLinkRepo.store) == 0


@pytest.mark.asyncio
async def test_link_request_blocks_independent_student_email() -> None:
    _FakeIndependentUserRepo.by_email["indie@example.com"] = object()

    async with _build_client(_parent_claims()) as client:
        resp = await client.post(
            "/api/v1/parents/me/link-requests",
            json={"student_email": "indie@example.com"},
        )
    assert resp.status_code == 422
    assert "Unable to send link request" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_student_lists_and_approves_pending_request() -> None:
    async with _build_client(_parent_claims()) as client:
        create_resp = await client.post(
            "/api/v1/parents/me/link-requests",
            json={"student_email": STUDENT.email},
        )
    link_id = create_resp.json()["data"]["id"]

    async with _build_client(_student_claims()) as client:
        list_resp = await client.get("/api/v1/students/me/link-requests")
        approve_resp = await client.post(f"/api/v1/students/me/link-requests/{link_id}/approve")

    assert list_resp.status_code == 200
    pending = list_resp.json()["data"]["pending"]
    assert len(pending) == 1
    assert pending[0]["parent_name"] == PARENT.display_name

    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["status"] == "approved"
    assert _FakeLinkRepo.store[link_id].status == ParentChildLinkStatus.APPROVED
    assert _FakeParentProfileRepo.store[PARENT.id].unlinked_since is None


@pytest.mark.asyncio
async def test_parent_connections_show_linked_state() -> None:
    link = ParentChildLink(
        parent_user_id=PARENT.id,
        student_user_id=STUDENT.id,
        status=ParentChildLinkStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    )
    link.created_at = datetime.now(timezone.utc)
    link.updated_at = link.created_at
    _FakeLinkRepo.store[link.id] = link
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link

    async with _build_client(_parent_claims()) as client:
        resp = await client.get("/api/v1/parents/me/connections")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["parent_state"] == "LINKED"
    assert data["links"][0]["status"] == "approved"
