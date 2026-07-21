#!/usr/bin/env python3
"""Real-Authentik E2E auth-suite seed (T-247, ARCH §6.4).

`scripts/seed_dev.py` seeds the Postgres side only, keyed on a FIXED
placeholder `authentik_id` string (e.g. "seed-platform-admin") — those rows
were never meant to complete a real OIDC login, since no matching Authentik
identity exists at that id. The T-247 `@auth @real` Playwright suite drives an
actual browser through Authentik's own login form, so it needs REAL,
loginable Authentik identities.

This script:
  1. Reuses `seed_dev.SEED_USERS` / `SEED_INDEPENDENT_USERS` as the source of
     truth for email/display_name/role/org-scope (avoids duplicating the
     9-role table in two files) — but ignores their placeholder
     `authentik_id`.
  2. For each, provisions (or reuses) a real Authentik user via
     `app.infrastructure.authentik.client` — the SAME client + calls already
     proven in production by the invite-accept and independent-signup flows
     (`create_user` / `set_password` / `activate_user`); `find_user_by_email`
     is the one new addition (see its docstring — unverified against a live
     instance).
  3. Rebuilds each seed spec with the REAL Authentik pk as `authentik_id`
     and upserts the Postgres/independent-schema row via `seed_dev`'s
     already-tested idempotent upsert functions.

Requires `AUTHENTIK_API_TOKEN` pointed at a real Authentik. Without it,
`get_authentik_client()` falls back to `DevAuthentikClient` (an in-memory
stub) — this script will run and log success, but no real Authentik user
exists, so a subsequent Playwright login attempt will fail. That's the
correct fail-mode for local dev without Authentik running; CI must set the
token once the compose stack + Authentik bootstrap are up (see T-247's
`.github/workflows/ci.yml` wiring).

Run (from repo root, after `docker compose up` + Authentik bootstrap):
    uv run python scripts/seed_e2e_auth_users.py

UNVERIFIED end-to-end: no Docker/Authentik is available in the environment
this script was written in, so the full round-trip (create → password → login
via Authentik's actual form) has not been exercised here. Each individual
Authentik API call mirrors an already-proven production call site except
`find_user_by_email` — confirm on first real run and adjust if needed.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
from pathlib import Path

# Mirrors seed_dev.py's own path shim — the app package lives under `api/`.
_API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
# scripts/ itself, for `import seed_dev` (both scripts are invoked as
# `uv run python scripts/<name>.py`, which puts this directory on sys.path[0]
# — this insert covers the case another script imports this one instead).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import structlog  # noqa: E402

import seed_dev  # noqa: E402
from app.features.academic_sessions.models import AcademicSession  # noqa: E402
from app.features.independent_users.models import IndependentUser  # noqa: E402
from app.features.schools.models import District, School  # noqa: E402
from app.features.users.models import User  # noqa: E402
from app.infrastructure.authentik.client import (  # noqa: E402
    AuthentikClientProtocol,
    get_authentik_client,
)

logger = structlog.get_logger(__name__)

# Dev/CI-only shared password for the seeded E2E identities — this script only
# ever targets ephemeral dev/CI Authentik instances (never production), so a
# labeled fallback default is acceptable (same convention as
# POSTGRES_PASSWORD=change_me_in_production in .env.example).
E2E_SEED_PASSWORD = os.environ.get(
    "E2E_SEED_PASSWORD", "IqbalAI-E2E-Seed-Dev-Only-2026!"
)


async def _provision_authentik_identity(
    client: AuthentikClientProtocol, *, email: str, display_name: str
) -> str:
    """Create-or-reuse a real, active, password-set Authentik identity.

    Returns the Authentik pk to use as the app-DB `authentik_id`.
    """
    existing_id = await client.find_user_by_email(email)
    if existing_id is not None:
        authentik_id = existing_id
        logger.info("e2e_authentik_user_reused", email=email, authentik_id=authentik_id)
    else:
        authentik_id = await client.create_user(
            email=email, name=display_name, is_active=False
        )
        logger.info(
            "e2e_authentik_user_created", email=email, authentik_id=authentik_id
        )

    # Idempotent regardless of create-vs-reuse: always (re-)set the known
    # password and ensure the account is active, so a re-run always leaves a
    # loginable identity even if a prior partial run left it half-provisioned.
    await client.set_password(authentik_id, E2E_SEED_PASSWORD)
    await client.activate_user(authentik_id)
    return authentik_id


async def provision_school_users(
    client: AuthentikClientProtocol,
) -> tuple[seed_dev.SeedUser, ...]:
    """Return SEED_USERS rebuilt with real Authentik pks as authentik_id."""
    provisioned = []
    for spec in seed_dev.SEED_USERS:
        real_id = await _provision_authentik_identity(
            client, email=spec.email, display_name=spec.display_name
        )
        provisioned.append(dataclasses.replace(spec, authentik_id=real_id))
    return tuple(provisioned)


async def provision_independent_users(
    client: AuthentikClientProtocol,
) -> tuple[seed_dev.SeedIndependentUser, ...]:
    """Return SEED_INDEPENDENT_USERS rebuilt with real Authentik pks."""
    provisioned = []
    for spec in seed_dev.SEED_INDEPENDENT_USERS:
        real_id = await _provision_authentik_identity(
            client, email=spec.email, display_name=spec.display_name
        )
        provisioned.append(dataclasses.replace(spec, authentik_id=real_id))
    return tuple(provisioned)


async def run() -> None:
    from sqlalchemy import select

    from app.db.session import async_session_factory

    client = get_authentik_client()

    school_users, independent_users = await asyncio.gather(
        provision_school_users(client),
        provision_independent_users(client),
    )

    async with async_session_factory() as session:

        async def get_district(district_id: str) -> District | None:
            res = await session.execute(
                select(District).where(District.id == district_id)
            )
            return res.scalar_one_or_none()

        async def get_school(school_id: str) -> School | None:
            res = await session.execute(select(School).where(School.id == school_id))
            return res.scalar_one_or_none()

        async def get_session_row(session_id: str) -> AcademicSession | None:
            res = await session.execute(
                select(AcademicSession).where(AcademicSession.id == session_id)
            )
            return res.scalar_one_or_none()

        async def persist_org(row: seed_dev.OrgRow) -> None:
            session.add(row)
            await session.flush()

        org_result = await seed_dev.seed_org(
            get_district, get_school, get_session_row, persist_org
        )

        async def get_existing_user(authentik_id: str) -> User | None:
            res = await session.execute(
                select(User).where(User.authentik_id == authentik_id)
            )
            return res.scalar_one_or_none()

        async def persist_user(user: User) -> None:
            session.add(user)

        user_result = await seed_dev.seed_users(
            school_users, get_existing_user, persist_user
        )

        async def get_existing_independent(authentik_id: str) -> IndependentUser | None:
            res = await session.execute(
                select(IndependentUser).where(
                    IndependentUser.authentik_id == authentik_id
                )
            )
            return res.scalar_one_or_none()

        async def persist_independent(user: IndependentUser) -> None:
            session.add(user)

        independent_result = await seed_dev.seed_independent_users(
            independent_users, get_existing_independent, persist_independent
        )
        await session.commit()

    logger.info(
        "seed_e2e_auth_users.complete",
        org_created=org_result.created,
        org_updated=org_result.updated,
        school_users_created=user_result.created,
        school_users_updated=user_result.updated,
        independent_users_created=independent_result.created,
        independent_users_updated=independent_result.updated,
        total_roles=len(school_users) + len(independent_users),
    )


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
