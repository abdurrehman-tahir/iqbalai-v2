"""Idempotency tests for the dev seed (T-228).

Loads `scripts/seed_dev.py` by path (it lives at the repo root, not under the
importable `app` package) and drives its DB-decoupled `seed_users` core with an
in-memory fake store — so idempotency is verified without a live Postgres.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_dev.py"


def _load_seed() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_dev", _SEED_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module defines `from __future__ import annotations`
    # dataclasses, whose annotation resolution looks the module up in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeStore:
    """In-memory stand-in for the users table keyed on authentik_id."""

    def __init__(self) -> None:
        self.by_authentik: dict[str, object] = {}

    async def get_existing(self, authentik_id: str) -> object | None:
        return self.by_authentik.get(authentik_id)

    async def persist(self, user: object) -> None:
        # mypy: User has an authentik_id attribute at runtime.
        self.by_authentik[user.authentik_id] = user  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_first_run_creates_full_demo_set() -> None:
    seed = _load_seed()
    store = _FakeStore()

    result = await seed.seed_users(seed.SEED_USERS, store.get_existing, store.persist)

    assert result.created == len(seed.SEED_USERS)
    assert result.updated == 0
    assert len(store.by_authentik) == len(seed.SEED_USERS)


@pytest.mark.asyncio
async def test_rerun_is_idempotent_no_duplicates() -> None:
    seed = _load_seed()
    store = _FakeStore()

    await seed.seed_users(seed.SEED_USERS, store.get_existing, store.persist)
    second = await seed.seed_users(seed.SEED_USERS, store.get_existing, store.persist)

    # Second run upserts in place — nothing new created, row count unchanged.
    assert second.created == 0
    assert second.updated == len(seed.SEED_USERS)
    assert len(store.by_authentik) == len(seed.SEED_USERS)


class _FakeOrgStore:
    """In-memory stand-in for the districts / schools / academic_sessions tables."""

    def __init__(self) -> None:
        self.rows: dict[str, object] = {}

    async def get(self, row_id: str) -> object | None:
        return self.rows.get(row_id)

    async def persist(self, row: object) -> None:
        self.rows[row.id] = row  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_seed_creates_the_org_rows_the_users_point_at() -> None:
    """QA E04/E06/E07/E08 — the demo IDs were stamped on users but never inserted.

    District Admin "create school" and School Admin "invite coordinator" 404'd on a
    district/school that did not exist, and the Coordinator had no active academic
    session, which blocked grades + subjects (and, downstream, the Teacher's profile).
    """
    seed = _load_seed()
    store = _FakeOrgStore()

    result = await seed.seed_org(store.get, store.get, store.get, store.persist)

    assert result.created == 3
    assert result.updated == 0

    district = store.rows[seed.DEMO_DISTRICT_ID]
    school = store.rows[seed.DEMO_SCHOOL_ID]
    session = store.rows[seed.DEMO_SESSION_ID]

    # The chain the users reference actually exists, and is wired together.
    assert school.district_id == seed.DEMO_DISTRICT_ID  # type: ignore[attr-defined]
    assert session.school_id == seed.DEMO_SCHOOL_ID  # type: ignore[attr-defined]
    assert district.name  # type: ignore[attr-defined]

    # An ACTIVE session is what unblocks grade/subject creation (E07/E08), and the
    # school's denormalized mirror must agree with it (T-042).
    assert session.is_active is True  # type: ignore[attr-defined]
    assert school.active_academic_session == session.label  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_seed_org_rerun_is_idempotent() -> None:
    seed = _load_seed()
    store = _FakeOrgStore()

    await seed.seed_org(store.get, store.get, store.get, store.persist)
    second = await seed.seed_org(store.get, store.get, store.get, store.persist)

    assert second.created == 0
    assert second.updated == 3
    assert len(store.rows) == 3


@pytest.mark.asyncio
async def test_seeded_users_point_at_the_seeded_org() -> None:
    """The two halves must agree — a user stamped with an ID no org row carries is the bug."""
    seed = _load_seed()
    store = _FakeOrgStore()

    await seed.seed_org(store.get, store.get, store.get, store.persist)

    for user in seed.SEED_USERS:
        if user.district_id is not None:
            assert user.district_id in store.rows, f"{user.email} points at a missing district"
        if user.school_id is not None:
            assert user.school_id in store.rows, f"{user.email} points at a missing school"


@pytest.mark.asyncio
async def test_demo_set_covers_the_hierarchy() -> None:
    seed = _load_seed()
    roles = {u.role.value for u in seed.SEED_USERS}

    # A usable demo dataset: bootstrap admin + a full district/school chain.
    for expected in (
        "platform_admin",
        "district_admin",
        "school_admin",
        "coordinator",
        "teacher",
        "student",
        "parent",
    ):
        assert expected in roles

    # The sample school/district IDs are stamped on the hierarchy users.
    student = next(u for u in seed.SEED_USERS if u.role.value == "student")
    assert student.school_id == seed.DEMO_SCHOOL_ID
    assert student.district_id == seed.DEMO_DISTRICT_ID


def test_parent_has_no_school_or_district_scope() -> None:
    """Parent access is via ParentChildLink, not org membership (T-247)."""
    seed = _load_seed()
    parent = next(u for u in seed.SEED_USERS if u.role.value == "parent")
    assert parent.school_id is None
    assert parent.district_id is None


# ---------------------------------------------------------------------------
# Independent-tenant users (T-247)
# ---------------------------------------------------------------------------


class _FakeIndependentStore:
    """In-memory stand-in for the `independent.users` table."""

    def __init__(self) -> None:
        self.by_authentik: dict[str, object] = {}

    async def get_existing(self, authentik_id: str) -> object | None:
        return self.by_authentik.get(authentik_id)

    async def persist(self, user: object) -> None:
        self.by_authentik[user.authentik_id] = user  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_independent_users_first_run_creates_full_set() -> None:
    seed = _load_seed()
    store = _FakeIndependentStore()

    result = await seed.seed_independent_users(
        seed.SEED_INDEPENDENT_USERS, store.get_existing, store.persist
    )

    assert result.created == len(seed.SEED_INDEPENDENT_USERS)
    assert result.updated == 0
    assert len(store.by_authentik) == len(seed.SEED_INDEPENDENT_USERS)


@pytest.mark.asyncio
async def test_independent_users_rerun_is_idempotent() -> None:
    seed = _load_seed()
    store = _FakeIndependentStore()

    await seed.seed_independent_users(
        seed.SEED_INDEPENDENT_USERS, store.get_existing, store.persist
    )
    second = await seed.seed_independent_users(
        seed.SEED_INDEPENDENT_USERS, store.get_existing, store.persist
    )

    assert second.created == 0
    assert second.updated == len(seed.SEED_INDEPENDENT_USERS)
    assert len(store.by_authentik) == len(seed.SEED_INDEPENDENT_USERS)


def test_independent_set_covers_both_independent_roles() -> None:
    seed = _load_seed()
    roles = {u.role.value for u in seed.SEED_INDEPENDENT_USERS}
    assert roles == {"independent_teacher", "independent_student"}


def test_full_seed_covers_all_nine_roles() -> None:
    """The union of SEED_USERS + SEED_INDEPENDENT_USERS is exactly the 9-role set
    frontend/src/lib/auth.ts's ALL_ROLES asserts (T-239) — kept as a plain string
    set here since this script cannot import frontend TS."""
    seed = _load_seed()
    roles = {u.role.value for u in seed.SEED_USERS} | {
        u.role.value for u in seed.SEED_INDEPENDENT_USERS
    }
    assert roles == {
        "platform_admin",
        "district_admin",
        "school_admin",
        "coordinator",
        "teacher",
        "student",
        "parent",
        "independent_teacher",
        "independent_student",
    }
