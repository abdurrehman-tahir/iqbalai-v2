#!/usr/bin/env python3
"""Idempotent development seed (T-228; extended T-247 for full role coverage).

Creates a reproducible demo dataset: the bootstrap Platform Admin plus one
sample district/school hierarchy (District Admin → School Admin → Coordinator →
Teacher → Student → Parent), plus the two independent-tenant roles (Independent
Teacher, Independent Student) — all 9 roles in the `Role` union. Used by the E2E
`e2e-smoke` job and for manual demos so the data is reproducible rather than
hand-made.

Postgres-only: `authentik_id` here is a fixed placeholder string, not a real
Authentik identity, so these rows alone cannot complete a real OIDC login. For
the T-247 `@auth @real` suite (which drives an actual Authentik login form),
see `scripts/seed_e2e_auth_users.py` — it provisions real Authentik identities
and seeds the matching DB rows keyed on Authentik's own assigned pk instead.

Idempotent: keyed on the unique ``authentik_id``. Re-running upserts (create if
missing, otherwise refresh mutable fields) so the DB ends in the same state no
matter how many times it runs — see ``test_seed_dev.py``.

Run (from repo root):
    uv run python scripts/seed_dev.py

The org hierarchy is seeded as real rows: district -> school -> active academic
session, then the users that point at them. This used to be ID-stamping only (the
tables did not exist in M-00/M-01), which left every seeded user referencing a
district and school that were absent from the DB — so District Admin "create school"
404'd, School Admin "invite coordinator" 404'd, and the Coordinator had no active
session for grades/subjects (QA E04/E06/E07/E08).
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

from app.features.academic_sessions.models import AcademicSession  # noqa: E402
from app.features.independent_users.models import IndependentUser, IndependentUserRole  # noqa: E402
from app.features.schools.models import District, School  # noqa: E402
from app.features.users.models import User, UserRole  # noqa: E402

logger = structlog.get_logger(__name__)

# Stable demo hierarchy IDs — fixed so re-runs and E2E assertions are reproducible.
DEMO_DISTRICT_ID = "d1000000-0000-4000-8000-000000000001"
DEMO_SCHOOL_ID = "5c000000-0000-4000-8000-000000000001"
DEMO_SESSION_ID = "5e550000-0000-4000-8000-000000000001"
# Coordinator grade/subject creation is gated on an ACTIVE session existing for the
# school; schools.active_academic_session is a denormalized mirror of this label (T-042).
DEMO_SESSION_LABEL = "2025-2026"
DEMO_DISTRICT_NAME = "Demo District"
DEMO_SCHOOL_NAME = "Demo School"

# Alembic school/0015 sample district + school (Authentik seed_dev_accounts points here).
# Without an active session on this school, OIDC school-scoped logins get 422 on /grades.
SAMPLE_DISTRICT_ID = "00000000-0000-0000-0000-0000000d1571"
SAMPLE_SCHOOL_ID = "00000000-0000-0000-0000-00000005c001"
SAMPLE_SESSION_ID = "00000000-0000-0000-0000-00000005e551"

OrgRow = District | School | AcademicSession


@dataclass(frozen=True)
class SeedUser:
    """A user to upsert. ``authentik_id`` is the idempotency key."""

    authentik_id: str
    email: str
    display_name: str
    role: UserRole
    school_id: str | None = None
    district_id: str | None = None
    # Coordinator scope = comma-separated grade names (flow-2); required to create grades.
    scoped_ids: str | None = None


# Demo coordinator may create/manage common K-12 grade names (Authentik seed matches).
DEMO_COORDINATOR_SCOPE = ",".join(f"Grade {n}" for n in range(1, 13))

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
        scoped_ids=DEMO_COORDINATOR_SCOPE,
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
    # T-247: Parent has no school/district scope of its own — access is via
    # ParentChildLink to a student, not org membership (ARCH §6.4 role table).
    SeedUser(
        authentik_id="seed-parent",
        email="parent@iqbalai.dev",
        display_name="Parent",
        role=UserRole.PARENT,
    ),
)


@dataclass(frozen=True)
class SeedIndependentUser:
    """An independent-tenant user to upsert (T-247). Independent users have no
    school/district scope — they live in the separate `independent` Postgres
    schema (ARCH §3.16) and are each their own micro-tenant."""

    authentik_id: str
    email: str
    display_name: str
    role: IndependentUserRole


# The two independent-tenant roles (school-tenant roles are in SEED_USERS above).
SEED_INDEPENDENT_USERS: tuple[SeedIndependentUser, ...] = (
    SeedIndependentUser(
        authentik_id="seed-independent-teacher",
        email="independent.teacher@iqbalai.dev",
        display_name="Independent Teacher",
        role=IndependentUserRole.INDEPENDENT_TEACHER,
    ),
    SeedIndependentUser(
        authentik_id="seed-independent-student",
        email="independent.student@iqbalai.dev",
        display_name="Independent Student",
        role=IndependentUserRole.INDEPENDENT_STUDENT,
    ),
)


@dataclass
class SeedResult:
    """Outcome of a seed run."""

    created: int = 0
    updated: int = 0


async def seed_org(
    get_district: Callable[[str], Awaitable[District | None]],
    get_school: Callable[[str], Awaitable[School | None]],
    get_session: Callable[[str], Awaitable[AcademicSession | None]],
    persist: Callable[[OrgRow], Awaitable[None]],
) -> SeedResult:
    """Upsert the demo district -> school -> active academic session chain.

    Written in FK order: ``schools.district_id`` and ``academic_sessions.school_id`` are
    both real FKs (ON DELETE RESTRICT). ``users.school_id`` / ``users.district_id`` are
    NOT — they are plain string columns, which is exactly why the seed could stamp them
    with IDs that had no matching rows and the DB never complained. The services do check,
    hence the 404s (QA E04/E06).

    Keyed on the fixed demo IDs, so re-running converges rather than duplicating.
    """
    result = SeedResult()

    district = await get_district(DEMO_DISTRICT_ID)
    if district is None:
        await persist(
            District(
                id=DEMO_DISTRICT_ID,
                name=DEMO_DISTRICT_NAME,
                region="Punjab",
                language_preference="en",
            )
        )
        result.created += 1
    else:
        district.name = DEMO_DISTRICT_NAME
        await persist(district)
        result.updated += 1

    school = await get_school(DEMO_SCHOOL_ID)
    if school is None:
        await persist(
            School(
                id=DEMO_SCHOOL_ID,
                district_id=DEMO_DISTRICT_ID,
                name=DEMO_SCHOOL_NAME,
                active_academic_session=DEMO_SESSION_LABEL,
            )
        )
        result.created += 1
    else:
        school.district_id = DEMO_DISTRICT_ID
        school.name = DEMO_SCHOOL_NAME
        school.active_academic_session = DEMO_SESSION_LABEL
        await persist(school)
        result.updated += 1

    session_row = await get_session(DEMO_SESSION_ID)
    if session_row is None:
        await persist(
            AcademicSession(
                id=DEMO_SESSION_ID,
                school_id=DEMO_SCHOOL_ID,
                label=DEMO_SESSION_LABEL,
                is_active=True,
            )
        )
        result.created += 1
    else:
        session_row.school_id = DEMO_SCHOOL_ID
        session_row.label = DEMO_SESSION_LABEL
        session_row.is_active = True
        await persist(session_row)
        result.updated += 1

    # Authentik local accounts (district.admin@…, school.admin@…) use the alembic
    # Sample School IDs — ensure that school also has an active session when present.
    sample_school = await get_school(SAMPLE_SCHOOL_ID)
    if sample_school is not None:
        sample_school.active_academic_session = DEMO_SESSION_LABEL
        await persist(sample_school)
        result.updated += 1
        sample_session = await get_session(SAMPLE_SESSION_ID)
        if sample_session is None:
            await persist(
                AcademicSession(
                    id=SAMPLE_SESSION_ID,
                    school_id=SAMPLE_SCHOOL_ID,
                    label=DEMO_SESSION_LABEL,
                    is_active=True,
                )
            )
            result.created += 1
        else:
            sample_session.school_id = SAMPLE_SCHOOL_ID
            sample_session.label = DEMO_SESSION_LABEL
            sample_session.is_active = True
            await persist(sample_session)
            result.updated += 1

    return result


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
                scoped_ids=spec.scoped_ids,
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
            existing.scoped_ids = spec.scoped_ids
            await persist(existing)
            result.updated += 1
    return result


async def seed_independent_users(
    seeds: Iterable[SeedIndependentUser],
    get_existing: Callable[[str], Awaitable[IndependentUser | None]],
    persist: Callable[[IndependentUser], Awaitable[None]],
) -> SeedResult:
    """Upsert independent-tenant `seeds` (T-247) — same shape as `seed_users`,
    decoupled from the DB session for unit testability."""
    result = SeedResult()
    for spec in seeds:
        existing = await get_existing(spec.authentik_id)
        if existing is None:
            user = IndependentUser(
                authentik_id=spec.authentik_id,
                email=spec.email,
                display_name=spec.display_name,
                role=spec.role,
            )
            await persist(user)
            result.created += 1
        else:
            existing.email = spec.email
            existing.display_name = spec.display_name
            existing.role = spec.role
            await persist(existing)
            result.updated += 1
    return result


async def run_seed() -> tuple[SeedResult, SeedResult, SeedResult]:
    """Open a real DB session and seed the demo dataset (org chain, then users).

    Independent users (T-247) share the same session — their model declares its
    own `schema="independent"` in `__table_args__`, so no separate connection or
    schema_translate_map is needed; SQLAlchemy qualifies the table name itself.
    """
    from sqlalchemy import select

    from app.db.session import async_session_factory

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

        async def persist_org(row: OrgRow) -> None:
            # Flush each org row as it is added. seed_org persists in FK order
            # (district -> school -> session), but the models carry no ORM relationship(),
            # so SQLAlchemy's unit of work will NOT reorder a batched flush to respect the
            # academic_sessions.school_id / schools.district_id FKs — flushing per row is
            # what guarantees each parent exists before its child inserts.
            session.add(row)
            await session.flush()

        org_result = await seed_org(
            get_district, get_school, get_session_row, persist_org
        )

        async def get_existing(authentik_id: str) -> User | None:
            res = await session.execute(
                select(User).where(User.authentik_id == authentik_id)
            )
            return res.scalar_one_or_none()

        async def persist(user: User) -> None:
            session.add(user)

        user_result = await seed_users(SEED_USERS, get_existing, persist)

        async def get_existing_independent(authentik_id: str) -> IndependentUser | None:
            res = await session.execute(
                select(IndependentUser).where(
                    IndependentUser.authentik_id == authentik_id
                )
            )
            return res.scalar_one_or_none()

        async def persist_independent(user: IndependentUser) -> None:
            session.add(user)

        independent_result = await seed_independent_users(
            SEED_INDEPENDENT_USERS, get_existing_independent, persist_independent
        )
        await session.commit()
    return org_result, user_result, independent_result


def main() -> None:
    org_result, user_result, independent_result = asyncio.run(run_seed())
    logger.info(
        "seed_dev.complete",
        org_created=org_result.created,
        org_updated=org_result.updated,
        created=user_result.created,
        updated=user_result.updated,
        independent_created=independent_result.created,
        independent_updated=independent_result.updated,
        total=len(SEED_USERS) + len(SEED_INDEPENDENT_USERS),
    )


if __name__ == "__main__":
    main()
