"""Real-Postgres test support for M-15 (T-186…T-194).

Runs only when ``DB_URL`` points at a migrated database (CI's backend-test job
sets it after ``alembic upgrade heads``); otherwise the tests skip. Each test
gets a disposable engine (CLAUDE.md rule 11) and a connection whose outer
transaction is ALWAYS rolled back — sessions join it with
``create_savepoint`` so service code may still commit / begin_nested freely
without leaving rows behind.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import _uuid7
from app.features.lectures.models import (
    LectureStatus,
    SchoolLecture,
    SchoolLectureParagraph,
    SchoolLectureSession,
    SchoolLectureVersion,
)
from app.features.schools.models import District, School
from app.features.student_questions.models import SchoolStudentQuestion
from app.features.users.models import User, UserAccountStatus, UserRole


def _load_all_models() -> None:
    """Register every feature model so cross-feature FKs resolve on flush, even
    when a test module is collected on its own (e.g. lectures → offerings)."""
    import app.features as features

    for mod in pkgutil.walk_packages(features.__path__, prefix="app.features."):
        leaf = mod.name.rsplit(".", 1)[-1]
        if ".tests" not in mod.name and (leaf == "models" or leaf.endswith("_models")):
            importlib.import_module(mod.name)


_load_all_models()


def _db_url() -> str | None:
    url = os.environ.get("DB_URL", "")
    return url if url.startswith("postgresql") else None


requires_pg = pytest.mark.skipif(_db_url() is None, reason="DB_URL not set (real Postgres)")


@pytest.fixture
async def pg() -> AsyncIterator[AsyncSession]:
    url = _db_url()
    if url is None:
        pytest.skip("DB_URL not set")
    engine = create_async_engine(url)
    try:
        conn = await engine.connect()
    except Exception as exc:  # unreachable DB in a dev env → skip, don't fail
        await engine.dispose()
        pytest.skip(f"Postgres unreachable: {exc}")
    outer = await conn.begin()
    factory = async_sessionmaker(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await outer.rollback()
        await conn.close()
        await engine.dispose()


def now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Seed:
    school_id: str
    student_id: str
    other_student_id: str
    teacher_id: str
    lecture_id: str
    version_id: str
    paragraph_id: str
    session_id: str
    paragraph_text: str


async def make_user(session: AsyncSession, *, role: UserRole, school_id: str | None) -> User:
    uid = _uuid7()
    user = User(
        id=uid,
        authentik_id=f"auth-{uid}",
        email=f"{uid}@example.test",
        display_name=f"{role.value} {uid[-4:]}",
        role=role,
        status=UserAccountStatus.ACTIVE,
        school_id=school_id,
    )
    session.add(user)
    await session.flush()
    return user


async def seed_lecture(
    session: AsyncSession,
    paragraph_text: str = "Force equals mass times acceleration. Newton's second law.",
) -> Seed:
    district = District(name="M15 District")
    session.add(district)
    await session.flush()
    school = School(name="M15 School", district_id=district.id)
    session.add(school)
    await session.flush()
    student = await make_user(session, role=UserRole.STUDENT, school_id=school.id)
    other = await make_user(session, role=UserRole.STUDENT, school_id=school.id)
    teacher = await make_user(session, role=UserRole.TEACHER, school_id=school.id)
    lecture = SchoolLecture(
        school_id=school.id,
        teacher_user_id=teacher.id,
        title="Newton",
        topic="Forces",
        status=LectureStatus.PUBLISHED,
    )
    session.add(lecture)
    await session.flush()
    version = SchoolLectureVersion(lecture_id=lecture.id, version=1, body=paragraph_text)
    session.add(version)
    await session.flush()
    lecture.current_version_id = version.id
    paragraph = SchoolLectureParagraph(
        lecture_version_id=version.id,
        ordinal=0,
        text=paragraph_text,
        # Must satisfy ParagraphSourceMetadata (extra=forbid) like real rows do.
        source_metadata_jsonb={"tier": "curriculum"},
    )
    session.add(paragraph)
    study = SchoolLectureSession(
        lecture_id=lecture.id,
        student_user_id=student.id,
        opened_at=now(),
        last_activity_at=now(),
    )
    session.add(study)
    await session.flush()
    return Seed(
        school_id=school.id,
        student_id=student.id,
        other_student_id=other.id,
        teacher_id=teacher.id,
        lecture_id=lecture.id,
        version_id=version.id,
        paragraph_id=paragraph.id,
        session_id=study.id,
        paragraph_text=paragraph_text,
    )


async def make_question(
    session: AsyncSession,
    seed: Seed,
    *,
    student_id: str | None = None,
    highlight_text: str | None = "mass",
) -> SchoolStudentQuestion:
    sid = student_id or seed.student_id
    study_id = seed.session_id
    if sid != seed.student_id:
        other_session = SchoolLectureSession(
            lecture_id=seed.lecture_id, student_user_id=sid, opened_at=now(), last_activity_at=now()
        )
        session.add(other_session)
        await session.flush()
        study_id = other_session.id
    question = SchoolStudentQuestion(
        student_user_id=sid,
        session_id=study_id,
        lecture_id=seed.lecture_id,
        highlight_text=highlight_text,
        question_text=f"Explain: {highlight_text}",
        paragraph_id=seed.paragraph_id,
        asked_at=now(),
    )
    session.add(question)
    await session.flush()
    return question
