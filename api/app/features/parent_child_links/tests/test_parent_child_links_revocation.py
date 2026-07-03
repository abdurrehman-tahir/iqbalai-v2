"""Revocation and multi-link tests — T-082."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus
from app.features.parent_child_links.tests.test_parent_child_links_api import (
    PARENT,
    PARENT_PROFILE,
    STUDENT,
    _build_client,
    _FakeIndependentUserRepo,
    _FakeLinkRepo,
    _FakeParentProfileRepo,
    _FakeUserRepo,
    _parent_claims,
    _student_claims,
)
from app.features.users.models import User, UserAccountStatus, UserRole

STUDENT2 = User(
    id="student-2",
    authentik_id="auth-student-2",
    email="student2@example.com",
    display_name="Student Two",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

PARENT2 = User(
    id="parent-2",
    authentik_id="auth-parent-2",
    email="parent2@example.com",
    display_name="Parent Two",
    role=UserRole.PARENT,
    status=UserAccountStatus.ACTIVE,
)


def _approved_link(parent_id: str, student_id: str) -> ParentChildLink:
    link = ParentChildLink(
        parent_user_id=parent_id,
        student_user_id=student_id,
        status=ParentChildLinkStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    )
    link.created_at = datetime.now(timezone.utc)
    link.updated_at = link.created_at
    return link


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {
        PARENT.id: PARENT,
        PARENT2.id: PARENT2,
        STUDENT.id: STUDENT,
        STUDENT2.id: STUDENT2,
    }
    _FakeUserRepo.by_email = {
        PARENT.email: PARENT,
        PARENT2.email: PARENT2,
        STUDENT.email: STUDENT,
        STUDENT2.email: STUDENT2,
    }
    _FakeParentProfileRepo.store = {PARENT.id: PARENT_PROFILE}
    _FakeLinkRepo.store = {}
    _FakeLinkRepo.by_pair = {}
    _FakeIndependentUserRepo.by_email = {}

    monkeypatch.setattr("app.features.parent_child_links.service.UserRepository", _FakeUserRepo)
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
    yield None


def _parent2_claims() -> dict[str, object]:
    return {
        "sub": PARENT2.authentik_id,
        "user_id": PARENT2.id,
        "role": PARENT2.role.value,
        "email": PARENT2.email,
        "tenant_type": "school",
    }


@pytest.mark.asyncio
async def test_parent_revokes_link_preserves_history() -> None:
    link = _approved_link(PARENT.id, STUDENT.id)
    _FakeLinkRepo.store[link.id] = link
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link

    async with _build_client(_parent_claims()) as client:
        resp = await client.post(f"/api/v1/parents/me/links/{link.id}/revoke")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "revoked"
    assert resp.json()["data"]["read_only_access"] is False
    assert _FakeLinkRepo.store[link.id].revoked_at is not None
    assert len(_FakeLinkRepo.store) == 1

    async with _build_client(_parent_claims()) as client:
        access = await client.get(f"/api/v1/parents/me/students/{STUDENT.id}/access-state")
        connections = await client.get("/api/v1/parents/me/connections")

    assert access.json()["data"]["access_state"] == "UNLINKED"
    assert access.json()["data"]["read_only_access"] is False
    assert connections.json()["data"]["parent_state"] == "PARENT_ACTIVE_UNLINKED"


@pytest.mark.asyncio
async def test_student_revokes_parent_link() -> None:
    link = _approved_link(PARENT.id, STUDENT.id)
    _FakeLinkRepo.store[link.id] = link
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link

    async with _build_client(_student_claims()) as client:
        resp = await client.post(f"/api/v1/students/me/links/{link.id}/revoke")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "revoked"

    async with _build_client(_student_claims()) as client:
        connections = await client.get("/api/v1/students/me/connections")

    data = connections.json()["data"]
    assert data["access_state"] == "UNLINKED"
    assert data["linked_parents"] == []
    assert len(data["link_history"]) == 1
    assert data["link_history"][0]["status"] == "revoked"


@pytest.mark.asyncio
async def test_parent_linked_to_two_students() -> None:
    link1 = _approved_link(PARENT.id, STUDENT.id)
    link2 = _approved_link(PARENT.id, STUDENT2.id)
    _FakeLinkRepo.store[link1.id] = link1
    _FakeLinkRepo.store[link2.id] = link2
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link1
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT2.id)] = link2

    async with _build_client(_parent_claims()) as client:
        access1 = await client.get(f"/api/v1/parents/me/students/{STUDENT.id}/access-state")
        access2 = await client.get(f"/api/v1/parents/me/students/{STUDENT2.id}/access-state")

    assert access1.json()["data"]["read_only_access"] is True
    assert access2.json()["data"]["read_only_access"] is True


@pytest.mark.asyncio
async def test_student_with_two_linked_parents() -> None:
    link1 = _approved_link(PARENT.id, STUDENT.id)
    link2 = _approved_link(PARENT2.id, STUDENT.id)
    _FakeLinkRepo.store[link1.id] = link1
    _FakeLinkRepo.store[link2.id] = link2
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link1
    _FakeLinkRepo.by_pair[(PARENT2.id, STUDENT.id)] = link2

    async with _build_client(_student_claims()) as client:
        resp = await client.get("/api/v1/students/me/connections")

    data = resp.json()["data"]
    assert data["access_state"] == "LINKED"
    assert len(data["linked_parents"]) == 2


@pytest.mark.asyncio
async def test_revoked_link_can_be_re_requested() -> None:
    link = _approved_link(PARENT.id, STUDENT.id)
    link.status = ParentChildLinkStatus.REVOKED
    link.revoked_at = datetime.now(timezone.utc)
    _FakeLinkRepo.store[link.id] = link
    _FakeLinkRepo.by_pair[(PARENT.id, STUDENT.id)] = link

    async with _build_client(_parent_claims()) as client:
        resp = await client.post(
            "/api/v1/parents/me/link-requests",
            json={"student_email": STUDENT.email},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["status"] == "pending"
    assert _FakeLinkRepo.store[link.id].status == ParentChildLinkStatus.PENDING
    assert _FakeLinkRepo.store[link.id].revoked_at is None
