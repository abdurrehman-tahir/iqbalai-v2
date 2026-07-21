"""Tests for the real-Authentik E2E seed (T-247).

Drives `provision_school_users` / `provision_independent_users` with a fake
Authentik client — no live Authentik or Postgres needed, mirroring
`test_seed_dev.py`'s DI-for-testability pattern.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_e2e_auth_users.py"
_SEED_DEV_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_dev.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_seed_e2e() -> ModuleType:
    # seed_e2e_auth_users.py does `import seed_dev` at module scope — load
    # seed_dev first so that import resolves against the same module instance
    # the test asserts against, rather than a second parallel load.
    _load(_SEED_DEV_PATH, "seed_dev")
    return _load(_SEED_PATH, "seed_e2e_auth_users")


class _FakeAuthentikClient:
    """In-memory fake standing in for AuthentikClientProtocol."""

    def __init__(self) -> None:
        self.by_email: dict[str, str] = {}
        self.passwords: dict[str, str] = {}
        self.active: set[str] = set()
        self._next_pk = 1

    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str:
        pk = f"real-authentik-pk-{self._next_pk}"
        self._next_pk += 1
        self.by_email[email] = pk
        if is_active:
            self.active.add(pk)
        return pk

    async def find_user_by_email(self, email: str) -> str | None:
        return self.by_email.get(email)

    async def activate_user(self, authentik_id: str) -> None:
        self.active.add(authentik_id)

    async def deactivate_user(self, authentik_id: str) -> None:
        self.active.discard(authentik_id)

    async def set_password(self, authentik_id: str, password: str) -> None:
        self.passwords[authentik_id] = password

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None:
        pass

    async def set_tenant_type(self, authentik_id: str, tenant_type: str) -> None:
        pass


@pytest.mark.asyncio
async def test_provision_school_users_creates_real_identities_for_every_seed_user() -> None:
    seed_e2e = _load_seed_e2e()
    client = _FakeAuthentikClient()

    provisioned = await seed_e2e.provision_school_users(client)

    assert len(provisioned) == len(seed_e2e.seed_dev.SEED_USERS)
    for original, result in zip(seed_e2e.seed_dev.SEED_USERS, provisioned, strict=True):
        # Real pk replaces the placeholder — never the fixed "seed-*" string.
        assert result.authentik_id != original.authentik_id
        assert result.authentik_id.startswith("real-authentik-pk-")
        assert result.email == original.email
        assert result.role == original.role
        # Every provisioned identity has a password set + is active (loginable).
        assert client.passwords[result.authentik_id] == seed_e2e.E2E_SEED_PASSWORD
        assert result.authentik_id in client.active


@pytest.mark.asyncio
async def test_provision_independent_users_creates_real_identities() -> None:
    seed_e2e = _load_seed_e2e()
    client = _FakeAuthentikClient()

    provisioned = await seed_e2e.provision_independent_users(client)

    assert len(provisioned) == len(seed_e2e.seed_dev.SEED_INDEPENDENT_USERS)
    for result in provisioned:
        assert result.authentik_id.startswith("real-authentik-pk-")
        assert result.authentik_id in client.active


@pytest.mark.asyncio
async def test_reprovisioning_reuses_the_existing_identity_not_a_duplicate() -> None:
    """Idempotent: a second run against the same (fake) Authentik must not
    create a second account for an email that already has one."""
    seed_e2e = _load_seed_e2e()
    client = _FakeAuthentikClient()

    first = await seed_e2e.provision_school_users(client)
    second = await seed_e2e.provision_school_users(client)

    first_ids = {u.authentik_id for u in first}
    second_ids = {u.authentik_id for u in second}
    assert first_ids == second_ids
    # Exactly one Authentik user per seed email, not two.
    assert len(client.by_email) == len(seed_e2e.seed_dev.SEED_USERS)


@pytest.mark.asyncio
async def test_reprovisioning_still_resets_password_and_activation() -> None:
    """A re-run must leave the identity loginable even if a prior partial run
    left it half-provisioned (e.g. password set but not yet activated)."""
    seed_e2e = _load_seed_e2e()
    client = _FakeAuthentikClient()

    await seed_e2e.provision_school_users(client)
    # Simulate drift: something deactivated the account since the last run.
    provisioned_id = next(iter(client.by_email.values()))
    client.active.discard(provisioned_id)

    await seed_e2e.provision_school_users(client)

    assert provisioned_id in client.active
