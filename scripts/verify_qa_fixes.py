#!/usr/bin/env python3
"""Verify the QA smoke-test fixes against a real database (QA report, 13 Jul 2026).

Checks, in order:
  E01        exam-framework actor columns hold a 64-char Authentik sub (were VARCHAR(36))
  E10/E11    an independent user can accept the ToS (was 404 "User profile not found")
  E10/E11    a failed accept leaves NO acceptance row behind (was committed mid-flight)
  E04/E06    the demo district + school the seeded users point at actually exist
  E07/E08    the demo school has an ACTIVE academic session (gates grades + subjects)

Run it INSIDE the api container — a host-installed Postgres listens on 127.0.0.1:5432 and
shadows Docker's, so from the host you get `role "iqbalai" does not exist`:

    docker compose exec api python /app/../scripts/verify_qa_fixes.py
    # or, since api/ is bind-mounted at /app:
    docker compose exec -T api python - < scripts/verify_qa_fixes.py

Prerequisites: `alembic upgrade heads` and `python scripts/seed_dev.py` have both run.
Exits 0 if every check passes, 1 otherwise. Creates a temporary independent user and
deletes it again; makes no other lasting change.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.exceptions import NotFoundError  # noqa: E402
from app.features.independent_users.models import (  # noqa: E402
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.independent_users.repository import IndependentUserRepository  # noqa: E402
from app.features.tos.repository import TosRepository  # noqa: E402
from app.features.tos.service import TosService  # noqa: E402

# The app's shared engine sets pool_pre_ping=True, which raises MissingGreenlet in a
# short-lived script. NullPool + no pre-ping sidesteps that.
engine = create_async_engine(get_settings().DB_URL, poolclass=NullPool, pool_pre_ping=False)
Session = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

# An Authentik `sub` is a 64-char hex hash, not a 36-char UUID.
SAMPLE_SUB = uuid.uuid4().hex * 2

DEMO_DISTRICT_ID = "d1000000-0000-4000-8000-000000000001"
DEMO_SCHOOL_ID = "5c000000-0000-4000-8000-000000000001"

failures: list[str] = []


def check(name: str, passed: bool, detail: str) -> None:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}: {detail}")
    if not passed:
        failures.append(name)


async def verify_e01() -> None:
    """E01 — created_by/approved_by must hold a 64-char sub, not truncate at 36."""
    print("\nE01 — exam-framework actor columns (was: StringDataRightTruncationError)")
    async with Session() as s:
        widths = await s.execute(
            text("""
                SELECT table_schema || '.' || table_name || '.' || column_name AS col,
                       character_maximum_length AS len
                FROM information_schema.columns
                WHERE table_name IN ('exam_frameworks', 'framework_study_plans')
                  AND column_name IN ('created_by', 'approved_by')
                ORDER BY 1
            """)
        )
        rows = widths.all()
        for col, length in rows:
            check(f"width {col}", length is not None and length >= 64, f"varchar({length})")

        # The exact write that used to 500: a real 64-char sub. Rolled back.
        try:
            await s.execute(
                text("""
                    INSERT INTO school.exam_frameworks
                      (id, name, exam_target, region, target_grade_range,
                       language, status, created_by, created_at, updated_at)
                    VALUES
                      (:id, 'verify probe', 'probe', 'Punjab', '{9,10}',
                       'en', 'draft', :sub, now(), now())
                """),
                {"id": str(uuid.uuid4()), "sub": SAMPLE_SUB},
            )
            stored = await s.execute(
                text("SELECT length(created_by) FROM school.exam_frameworks WHERE created_by = :s"),
                {"s": SAMPLE_SUB},
            )
            check("insert 64-char sub", stored.scalar() == 64, "stored at full length")
        except Exception as exc:  # noqa: BLE001 — the check is precisely "does this raise"
            check("insert 64-char sub", False, f"{type(exc).__name__}: {exc}")
        finally:
            await s.rollback()


async def verify_tos_independent() -> None:
    """E10/E11 — an independent user must be able to accept the ToS."""
    print("\nE10/E11 — independent ToS acceptance (was: 404 User profile not found)")
    async with Session() as s:
        tos = await TosRepository(s).get_current_tos()
        if tos is None:
            check("current ToS exists", False, "no ToS version published — cannot verify")
            return
        tos_id = tos.id

        user = await IndependentUserRepository(s).create(
            IndependentUser(
                authentik_id=SAMPLE_SUB,
                email=f"verify-{SAMPLE_SUB[:8]}@qa.local",
                display_name="Verify Independent Teacher",
                role=IndependentUserRole.INDEPENDENT_TEACHER,
                status=IndependentUserAccountStatus.ACTIVE,
                language_preference="en",
            )
        )
        await s.commit()
        uid = user.id

        absent = await s.execute(
            text("SELECT count(*) FROM school.users WHERE authentik_id = :s"), {"s": SAMPLE_SUB}
        )
        check(
            "user is independent-only", absent.scalar() == 0, "no row in school.users, as expected"
        )

    try:
        # The pre-fix path: resolve an independent user against school.users.
        async with Session() as s:
            raised = False
            try:
                await TosService(s).accept_tos(uid, tos_id, None, tenant_type="school")
            except NotFoundError:
                raised = True
            check("school lookup still rejects", raised, "NotFoundError — the old 404")

        # Atomicity: that failure must not have left an acceptance row behind.
        async with Session() as s:
            orphan = await s.execute(
                text("SELECT count(*) FROM school.user_tos_acceptances WHERE user_id = :u"),
                {"u": uid},
            )
            check("failed accept wrote nothing", orphan.scalar() == 0, "no orphan acceptance row")

        # The fixed path.
        async with Session() as s:
            acc = await TosService(s).accept_tos(
                uid, tos_id, "127.0.0.1", tenant_type="independent"
            )
            await s.commit()
            check(
                "independent accept succeeds",
                acc.user_id == uid,
                f"acceptance at {acc.accepted_at}",
            )

        async with Session() as s:
            row = await s.execute(
                text("SELECT count(*) FROM school.user_tos_acceptances WHERE user_id = :u"),
                {"u": uid},
            )
            check("acceptance persisted", row.scalar() == 1, "exactly one row")
    finally:
        async with Session() as s:
            await s.execute(
                text("DELETE FROM school.user_tos_acceptances WHERE user_id = :u"), {"u": uid}
            )
            await s.execute(text("DELETE FROM independent.users WHERE id = :u"), {"u": uid})
            await s.commit()
            print("  ....  cleanup: temporary independent user removed")


async def verify_seeded_org() -> None:
    """E04/E06/E07/E08 — the org rows the seeded users point at must exist."""
    print("\nE04/E06/E07/E08 — seeded org hierarchy (was: district/school not found)")
    async with Session() as s:
        d = await s.execute(
            text("SELECT count(*) FROM school.districts WHERE id = :i"), {"i": DEMO_DISTRICT_ID}
        )
        check("demo district exists", d.scalar() == 1, DEMO_DISTRICT_ID)

        sc = await s.execute(
            text("SELECT count(*) FROM school.schools WHERE id = :i AND district_id = :d"),
            {"i": DEMO_SCHOOL_ID, "d": DEMO_DISTRICT_ID},
        )
        check("demo school exists", sc.scalar() == 1, f"{DEMO_SCHOOL_ID} under the district")

        act = await s.execute(
            text("""
                SELECT label FROM school.academic_sessions
                WHERE school_id = :s AND is_active IS TRUE AND deleted_at IS NULL
            """),
            {"s": DEMO_SCHOOL_ID},
        )
        label = act.scalar()
        check(
            "active academic session", label is not None, f"label={label!r} (gates grades/subjects)"
        )

        orphans = await s.execute(
            text("""
                SELECT count(*) FROM school.users u
                WHERE u.school_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM school.schools s WHERE s.id = u.school_id)
            """)
        )
        check("no users point at a missing school", orphans.scalar() == 0, "referential sanity")


async def main() -> int:
    print(f"Verifying QA fixes against {get_settings().DB_URL.split('@')[-1]}")
    await verify_e01()
    await verify_tos_independent()
    await verify_seeded_org()
    await engine.dispose()

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED ({len(failures)}): " + ", ".join(failures))
        return 1
    print("All QA fix checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
