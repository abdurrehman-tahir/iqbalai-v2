"""Permission inheritance matrix integration tests — T-036.

Validates Flow 2 v3 §4 permission matrix cells against M-02 implemented endpoints.
Uses the real v1 router + ``require_role`` + service scope checks with in-memory
fake repositories (no Postgres). Rows for subjects/grades/bulk-import are deferred
to M-03/M-06 when those endpoints exist.
"""

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
from app.core.tests.test_idempotency import FakeRedis
from app.features.invites.models import UserInvite, UserInviteStatus
from app.features.schools.models import District, School
from app.features.users.models import User, UserAccountStatus, UserRole
from app.infrastructure.authentik.client import DevAuthentikClient

# ── Shared fake repositories ─────────────────────────────────────────────────


class _FakeDistrictRepo:
    store: dict[str, District] = {
        "dist-1": District(id="dist-1", name="District 1", region="Punjab"),
        "dist-2": District(id="dist-2", name="District 2", region="Sindh"),
    }

    def __init__(self, session: Any) -> None:
        pass

    async def list_districts(self) -> list[District]:
        return [d for d in self.store.values() if d.deleted_at is None]

    async def get_by_id(self, id: str) -> District | None:
        return self.store.get(id)

    async def get_active_by_name(self, name: str) -> District | None:
        return next(
            (d for d in self.store.values() if d.name == name and d.deleted_at is None),
            None,
        )

    async def create(self, district: District) -> District:
        now = datetime.now(timezone.utc)
        district.created_at = now
        district.updated_at = now
        self.store[district.id] = district
        return district

    async def update(self, district: District) -> District:
        return district

    async def soft_delete(self, district: District) -> None:
        district.deleted_at = datetime.now(timezone.utc)


class _FakeSchoolRepo:
    store: dict[str, School] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_schools(self, district_id: str | None = None) -> list[School]:
        schools = [s for s in self.store.values() if s.deleted_at is None]
        if district_id is not None:
            schools = [s for s in schools if s.district_id == district_id]
        return schools

    async def get_by_id(self, id: str) -> School | None:
        return self.store.get(id)

    async def get_active_by_name_in_district(self, district_id: str, name: str) -> School | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.district_id == district_id and s.name == name and s.deleted_at is None
            ),
            None,
        )

    async def create(self, school: School) -> School:
        now = datetime.now(timezone.utc)
        school.created_at = now
        school.updated_at = now
        self.store[school.id] = school
        return school

    async def update(self, school: School) -> School:
        return school

    async def soft_delete(self, school: School) -> None:
        school.deleted_at = datetime.now(timezone.utc)


class _FakeInviteRepo:
    store: dict[str, UserInvite] = {}
    by_token: dict[str, UserInvite] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, invite_id: str) -> UserInvite | None:
        return self.store.get(invite_id)

    async def get_by_token_hash(self, token_hash: str) -> UserInvite | None:
        return self.by_token.get(token_hash)

    async def get_pending_by_email(self, email: str) -> UserInvite | None:
        return next(
            (
                i
                for i in self.store.values()
                if i.email == email.lower() and i.status == UserInviteStatus.PENDING
            ),
            None,
        )

    async def create(self, invite: UserInvite) -> UserInvite:
        now = datetime.now(timezone.utc)
        invite.created_at = now
        invite.updated_at = now
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def update(self, invite: UserInvite) -> UserInvite:
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def expire_stale_pending(self, invite: UserInvite) -> tuple[UserInvite, bool]:
        return invite, False


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        user = self.users.get(user_id)
        if user is None or user.deleted_at is not None:
            return None
        return user

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next(
            (
                u
                for u in self.users.values()
                if u.authentik_id == authentik_id and u.deleted_at is None
            ),
            None,
        )

    async def get_by_authentik_id_any(self, authentik_id: str) -> User | None:
        return next((u for u in self.users.values() if u.authentik_id == authentik_id), None)

    async def get_by_email(self, email: str) -> User | None:
        return next(
            (u for u in self.users.values() if u.email == email.lower() and u.deleted_at is None),
            None,
        )

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def update(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def list_scoped(
        self,
        *,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> list[User]:
        rows = [u for u in self.users.values() if u.deleted_at is None]
        if school_id is not None:
            return [u for u in rows if u.school_id == school_id]
        if district_id is not None:
            return [u for u in rows if u.district_id == district_id]
        return rows

    async def count_active_admins(
        self,
        *,
        role: UserRole,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> int:
        count = 0
        for user in self.users.values():
            if user.deleted_at is not None:
                continue
            if user.status != UserAccountStatus.ACTIVE or user.role != role:
                continue
            if role == UserRole.PLATFORM_ADMIN:
                if user.district_id is None and user.school_id is None:
                    count += 1
            elif role == UserRole.DISTRICT_ADMIN and user.district_id == district_id:
                count += 1
            elif role == UserRole.SCHOOL_ADMIN and user.school_id == school_id:
                count += 1
        return count


def _seed_schools() -> None:
    now = datetime.now(timezone.utc)
    _FakeSchoolRepo.store = {
        "school-1": School(
            id="school-1",
            district_id="dist-1",
            name="School One",
            created_at=now,
            updated_at=now,
        ),
        "school-2": School(
            id="school-2",
            district_id="dist-2",
            name="School Two",
            created_at=now,
            updated_at=now,
        ),
    }


def _seed_users() -> None:
    now = datetime.now(timezone.utc)
    _FakeUserRepo.users = {
        "teacher-1": User(
            id="teacher-1",
            authentik_id="ak-teacher-1",
            email="teacher@test.com",
            display_name="Teacher",
            role=UserRole.TEACHER,
            status=UserAccountStatus.ACTIVE,
            school_id="school-1",
            district_id="dist-1",
            created_at=now,
            updated_at=now,
        ),
        "sa-1": User(
            id="sa-1",
            authentik_id="ak-sa-1",
            email="sa@test.com",
            display_name="School Admin",
            role=UserRole.SCHOOL_ADMIN,
            status=UserAccountStatus.ACTIVE,
            school_id="school-1",
            district_id="dist-1",
            created_at=now,
            updated_at=now,
        ),
        "sa-2": User(
            id="sa-2",
            authentik_id="ak-sa-2",
            email="sa2@test.com",
            display_name="School Admin 2",
            role=UserRole.SCHOOL_ADMIN,
            status=UserAccountStatus.ACTIVE,
            school_id="school-2",
            district_id="dist-2",
            created_at=now,
            updated_at=now,
        ),
    }


@pytest.fixture(autouse=True)
def _patch_all(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeInviteRepo.store = {}
    _FakeInviteRepo.by_token = {}
    _seed_schools()
    _seed_users()

    monkeypatch.setattr("app.features.schools.service.DistrictRepository", _FakeDistrictRepo)
    monkeypatch.setattr("app.features.schools.service.SchoolRepository", _FakeSchoolRepo)
    monkeypatch.setattr("app.features.invites.service.UserInviteRepository", _FakeInviteRepo)
    monkeypatch.setattr("app.features.invites.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.invites.service.DistrictRepository", _FakeDistrictRepo)
    monkeypatch.setattr("app.features.invites.service.SchoolRepository", _FakeSchoolRepo)
    monkeypatch.setattr("app.features.users.lifecycle_service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.schools.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.users.lifecycle_service.audit", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.send_invite_email", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.notify_account_event", AsyncMock())
    monkeypatch.setattr(
        "app.features.invites.service.get_authentik_client", lambda: DevAuthentikClient()
    )
    monkeypatch.setattr("app.features.invites.service.get_redis", lambda: FakeRedis())
    monkeypatch.setattr(
        "app.features.users.lifecycle_service.get_authentik_client",
        lambda: AsyncMock(deactivate_user=AsyncMock(), activate_user=AsyncMock()),
    )


def _build_client(
    role: str,
    *,
    district_id: str | None = "dist-1",
    school_id: str | None = None,
) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        data: dict[str, object] = {"sub": f"ak-{role}", "role": role}
        if district_id is not None:
            data["district_id"] = district_id
        if school_id is not None:
            data["school_id"] = school_id
        return data

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── Matrix: Flow 2 §4 rows implemented in M-02 ────────────────────────────────

MatrixCase = tuple[str, str, int, dict[str, str | None]]


CREATE_DISTRICT_CASES: list[MatrixCase] = [
    ("create_district", "platform_admin", 201, {}),
    ("create_district", "district_admin", 403, {}),
    ("create_district", "school_admin", 403, {}),
    ("create_district", "coordinator", 403, {}),
    ("create_district", "teacher", 403, {}),
]

CREATE_SCHOOL_CASES: list[MatrixCase] = [
    ("create_school", "platform_admin", 201, {}),
    ("create_school", "district_admin", 201, {"district_id": "dist-1"}),
    ("create_school", "school_admin", 403, {"district_id": "dist-1", "school_id": "school-1"}),
    ("create_school", "coordinator", 403, {"school_id": "school-1"}),
    ("create_school", "teacher", 403, {}),
]

INVITE_SCHOOL_ADMIN_CASES: list[MatrixCase] = [
    ("invite_school_admin", "platform_admin", 201, {}),
    ("invite_school_admin", "district_admin", 201, {"district_id": "dist-1"}),
    (
        "invite_school_admin",
        "school_admin",
        422,
        {"district_id": "dist-1", "school_id": "school-1"},
    ),
    ("invite_school_admin", "coordinator", 403, {"school_id": "school-1"}),
]

INVITE_COORDINATOR_CASES: list[MatrixCase] = [
    ("invite_coordinator", "platform_admin", 201, {}),
    ("invite_coordinator", "district_admin", 201, {"district_id": "dist-1"}),
    ("invite_coordinator", "school_admin", 201, {"district_id": "dist-1", "school_id": "school-1"}),
    ("invite_coordinator", "coordinator", 403, {"school_id": "school-1"}),
    ("invite_coordinator", "teacher", 403, {}),
]

INVITE_TEACHER_CASES: list[MatrixCase] = [
    ("invite_teacher", "platform_admin", 201, {}),
    ("invite_teacher", "district_admin", 201, {"district_id": "dist-1"}),
    ("invite_teacher", "school_admin", 201, {"district_id": "dist-1", "school_id": "school-1"}),
    ("invite_teacher", "coordinator", 403, {"school_id": "school-1"}),
]

LIST_USERS_CASES: list[MatrixCase] = [
    ("list_users", "platform_admin", 200, {}),
    ("list_users", "district_admin", 200, {"district_id": "dist-1"}),
    ("list_users", "school_admin", 200, {"district_id": "dist-1", "school_id": "school-1"}),
    ("list_users", "coordinator", 403, {"school_id": "school-1"}),
    ("list_users", "teacher", 403, {}),
]

SUSPEND_USER_CASES: list[MatrixCase] = [
    ("suspend_user", "platform_admin", 200, {}),
    ("suspend_user", "district_admin", 200, {"district_id": "dist-1"}),
    ("suspend_user", "school_admin", 200, {"district_id": "dist-1", "school_id": "school-1"}),
    ("suspend_user", "coordinator", 403, {"school_id": "school-1"}),
]

ALL_MATRIX_CASES = (
    CREATE_DISTRICT_CASES
    + CREATE_SCHOOL_CASES
    + INVITE_SCHOOL_ADMIN_CASES
    + INVITE_COORDINATOR_CASES
    + INVITE_TEACHER_CASES
    + LIST_USERS_CASES
    + SUSPEND_USER_CASES
)


async def _execute_action(
    client: AsyncClient,
    action: str,
    *,
    suffix: str,
) -> Any:
    if action == "create_district":
        return await client.post(
            "/api/v1/admin/districts/",
            json={"name": f"Matrix District {suffix}", "region": "Test"},
        )
    if action == "create_school":
        return await client.post(
            "/api/v1/admin/schools/",
            json={"name": f"Matrix School {suffix}", "district_id": "dist-1"},
        )
    if action == "invite_school_admin":
        return await client.post(
            "/api/v1/admin/users",
            json={
                "email": f"sa-{suffix}@matrix.test",
                "display_name": "Matrix SA",
                "role": "school_admin",
                "school_id": "school-1",
            },
        )
    if action == "invite_coordinator":
        return await client.post(
            "/api/v1/admin/users",
            json={
                "email": f"coord-{suffix}@matrix.test",
                "display_name": "Matrix Coord",
                "role": "coordinator",
                "school_id": "school-1",
                "grade_scope": ["Grade 9"],
            },
        )
    if action == "invite_teacher":
        return await client.post(
            "/api/v1/admin/users",
            json={
                "email": f"teacher-{suffix}@matrix.test",
                "display_name": "Matrix Teacher",
                "role": "teacher",
                "school_id": "school-1",
            },
        )
    if action == "list_users":
        return await client.get("/api/v1/admin/users/")
    if action == "suspend_user":
        return await client.post("/api/v1/admin/users/teacher-1/suspend")
    raise ValueError(f"Unknown action: {action}")


@pytest.mark.parametrize(
    ("action", "role", "expected_status", "scope"),
    ALL_MATRIX_CASES,
    ids=[f"{a}-{r}-{s}" for a, r, s, _ in ALL_MATRIX_CASES],
)
async def test_permission_matrix_cell(
    action: str,
    role: str,
    expected_status: int,
    scope: dict[str, str | None],
) -> None:
    """Each cell: role × action → expected HTTP status per Flow 2 §4."""
    suffix = f"{action}-{role}"
    async with _build_client(
        role,
        district_id=scope.get("district_id", "dist-1" if role != "platform_admin" else None),
        school_id=scope.get("school_id"),
    ) as client:
        resp = await _execute_action(client, action, suffix=suffix)
    assert resp.status_code == expected_status, (
        f"{action} as {role}: expected {expected_status}, got {resp.status_code} "
        f"({resp.text[:200]})"
    )


async def test_inheritance_platform_admin_creates_school() -> None:
    """§6.19: Platform Admin inherits District Admin school-creation rights."""
    async with _build_client("platform_admin", district_id=None) as client:
        resp = await client.post(
            "/api/v1/admin/schools/",
            json={"name": "Inherited School", "district_id": "dist-1"},
        )
    assert resp.status_code == 201


async def test_cross_district_school_get_returns_404() -> None:
    """§3.13: cross-tenant school access → 404, not 403."""
    async with _build_client("district_admin", district_id="dist-1") as client:
        resp = await client.get("/api/v1/admin/schools/school-2")
    assert resp.status_code == 404


async def test_cross_school_suspend_returns_404() -> None:
    """School Admin from school-2 cannot suspend user in school-1."""
    async with _build_client("school_admin", district_id="dist-2", school_id="school-2") as client:
        resp = await client.post("/api/v1/admin/users/teacher-1/suspend")
    assert resp.status_code == 404


async def test_platform_admin_cross_district_school_get_allowed() -> None:
    """Platform Admin bypasses district scope."""
    async with _build_client("platform_admin", district_id=None) as client:
        resp = await client.get("/api/v1/admin/schools/school-2")
    assert resp.status_code == 200
