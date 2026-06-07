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
    ):
        assert expected in roles

    # The sample school/district IDs are stamped on the hierarchy users.
    student = next(u for u in seed.SEED_USERS if u.role.value == "student")
    assert student.school_id == seed.DEMO_SCHOOL_ID
    assert student.district_id == seed.DEMO_DISTRICT_ID
