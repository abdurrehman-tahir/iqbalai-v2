#!/usr/bin/env python3
"""Idempotent development seed (T-228).

Creates a reproducible demo dataset: the bootstrap Platform Admin plus one
sample district/school hierarchy (District Admin → School Admin → Coordinator →
Teacher → Student). Used by the E2E `e2e-smoke` job and for manual demos so the
data is reproducible rather than hand-made.

Idempotent: keyed on the unique ``authentik_id``. Re-running upserts (create if
missing, otherwise refresh mutable fields) so the DB ends in the same state no
matter how many times it runs — see ``test_seed_dev.py``.

Run (from repo root):
    uv run python scripts/seed_dev.py

NOTE on the hierarchy: M-00/M-01 have no ``schools``/``districts`` tables yet —
``users.school_id`` / ``users.district_id`` are plain nullable string columns
(no FK target). So "one sample district/school" is modelled as the two stable
demo IDs below stamped onto the seeded user rows. When the hierarchy tables land
(later milestone) this seed gains rows for them; the user wiring stays the same.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

# The script is invoked from the repo root (`uv run python scripts/seed_dev.py`)
# but the app package lives under ``api/`` — put it on the path before importing.
_API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

import structlog  # noqa: E402  (import after sys.path shim)

from app.features.users.models import User, UserRole  # noqa: E402

logger = structlog.get_logger(__name__)

# Stable demo hierarchy IDs — fixed so re-runs and E2E assertions are reproducible.
DEMO_DISTRICT_ID = "d1000000-0000-4000-8000-000000000001"
DEMO_SCHOOL_ID = "5c000000-0000-4000-8000-000000000001"


@dataclass(frozen=True)
class SeedUser:
    """A user to upsert. ``authentik_id`` is the idempotency key."""

    authentik_id: str
    email: str
    display_name: str
    role: UserRole
    school_id: str | None = None
    district_id: str | None = None


# The reproducible demo set: bootstrap admin + one full district/school chain.
SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(
        authentik_id="seed-platform-admin",
        email="admin@iqbalai.dev",
        display_name="Platform Admin",
        role=UserRole.PLATFORM_ADMIN,
    ),
    SeedUser(
        authentik_id="seed-district-admin",
        email="district.admin@iqbalai.dev",
        display_name="District Admin",
        role=UserRole.DISTRICT_ADMIN,
        district_id=DEMO_DISTRICT_ID,
    ),
    SeedUser(
        authentik_id="seed-school-admin",
        email="school.admin@iqbalai.dev",
        display_name="School Admin",
        role=UserRole.SCHOOL_ADMIN,
        school_id=DEMO_SCHOOL_ID,
        district_id=DEMO_DISTRICT_ID,
    ),
    SeedUser(
        authentik_id="seed-coordinator",
        email="coordinator@iqbalai.dev",
        display_name="Coordinator",
        role=UserRole.COORDINATOR,
        school_id=DEMO_SCHOOL_ID,
        district_id=DEMO_DISTRICT_ID,
    ),
    SeedUser(
        authentik_id="seed-teacher",
        email="teacher@iqbalai.dev",
        display_name="Teacher",
        role=UserRole.TEACHER,
        school_id=DEMO_SCHOOL_ID,
        district_id=DEMO_DISTRICT_ID,
    ),
    SeedUser(
        authentik_id="seed-student",
        email="student@iqbalai.dev",
        display_name="Student",
        role=UserRole.STUDENT,
        school_id=DEMO_SCHOOL_ID,
        district_id=DEMO_DISTRICT_ID,
    ),
)


@dataclass
class SeedResult:
    """Outcome of a seed run."""

    created: int = 0
    updated: int = 0


async def seed_users(
    seeds: Iterable[SeedUser],
    get_existing: Callable[[str], Awaitable[User | None]],
    persist: Callable[[User], Awaitable[None]],
) -> SeedResult:
    """Upsert ``seeds`` via the injected lookup + persist callbacks.

    Decoupled from the DB session so the idempotency logic is unit-testable with
    an in-memory fake (no Postgres needed) — see ``test_seed_dev.py``.
    """
    result = SeedResult()
    for spec in seeds:
        existing = await get_existing(spec.authentik_id)
        if existing is None:
            user = User(
                authentik_id=spec.authentik_id,
                email=spec.email,
                display_name=spec.display_name,
                role=spec.role,
                school_id=spec.school_id,
                district_id=spec.district_id,
            )
            await persist(user)
            result.created += 1
        else:
            # Refresh mutable fields so a changed spec converges (still idempotent
            # for an unchanged spec — same input ⇒ same end state).
            existing.email = spec.email
            existing.display_name = spec.display_name
            existing.role = spec.role
            existing.school_id = spec.school_id
            existing.district_id = spec.district_id
            await persist(existing)
            result.updated += 1
    return result


async def run_seed() -> SeedResult:
    """Open a real DB session and seed the demo dataset."""
    from sqlalchemy import select

    from app.db.session import async_session_factory

    async with async_session_factory() as session:

        async def get_existing(authentik_id: str) -> User | None:
            res = await session.execute(select(User).where(User.authentik_id == authentik_id))
            return res.scalar_one_or_none()

        async def persist(user: User) -> None:
            session.add(user)

        result = await seed_users(SEED_USERS, get_existing, persist)
        await session.commit()
    return result


def main() -> None:
    result = asyncio.run(run_seed())
    logger.info(
        "seed_dev.complete",
        created=result.created,
        updated=result.updated,
        total=len(SEED_USERS),
    )


if __name__ == "__main__":
    main()
