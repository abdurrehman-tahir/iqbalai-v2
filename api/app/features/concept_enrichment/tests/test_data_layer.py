"""T-189 — concept_applications cache, careers vocabulary, simulation progress."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import UniqueConstraint, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.base import Base
from app.features.concept_enrichment import cache
from app.features.concept_enrichment.models import (
    Career,
    ConceptApplicationStatus,
    EnrichmentTenantType,
    SchoolConceptApplication,
    SchoolStudentSimulationProgress,
)
from app.features.concept_enrichment.repository import SimulationProgressRepository
from app.features.student_highlights.tests.pg_support import requires_pg, seed_lecture
from app.tasks.beat_schedule import BEAT_SCHEDULE

_VERSIONS = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school"


def _load_seed() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "seed_careers", _VERSIONS / "0076_seed_careers.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- models -------------------------------------------------------------------------


def test_tables_registered_in_school_schema() -> None:
    for name in ("careers", "concept_applications", "student_simulation_progress"):
        assert f"school.{name}" in Base.metadata.tables


def test_concept_applications_is_per_concept_not_per_student() -> None:
    table = Base.metadata.tables["school.concept_applications"]
    cols = {c.name for c in table.columns}
    assert {
        "id",
        "concept_id",
        "real_world_uses",
        "career_link_ids",
        "mini_sim_prompt",
        "generated_at",
        "tenant_type",
    } <= cols
    assert "student_user_id" not in cols
    uq = {
        tuple(c.name for c in con.columns)
        for con in table.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("concept_id", "tenant_type") in uq


def test_simulation_progress_is_per_student() -> None:
    table = Base.metadata.tables["school.student_simulation_progress"]
    cols = {c.name for c in table.columns}
    assert {"id", "student_user_id", "concept_id", "sim_state", "updated_at", "tenant_type"} <= cols
    fks = {fk.parent.name: fk.ondelete for fk in table.foreign_keys}
    assert fks == {"student_user_id": "CASCADE"}


def test_careers_shape() -> None:
    cols = {c.name for c in Base.metadata.tables["school.careers"].columns}
    assert {"id", "name", "sector", "required_concepts"} <= cols


def test_model_defaults() -> None:
    row = SchoolConceptApplication(concept_id="forces", concept_label="Forces")
    assert row.status == ConceptApplicationStatus.PENDING
    assert row.tenant_type == EnrichmentTenantType.SCHOOL
    assert row.real_world_uses == [] and row.career_link_ids == []


# --- migrations / seed ---------------------------------------------------------------


def test_migration_chain() -> None:
    chain = [
        ("0075_careers.py", "school_0075", "school_0074"),
        ("0076_seed_careers.py", "school_0076", "school_0075"),
        ("0077_concept_applications.py", "school_0077", "school_0076"),
        ("0078_student_simulation_progress.py", "school_0078", "school_0077"),
    ]
    for fname, rev, down in chain:
        text = (_VERSIONS / fname).read_text(encoding="utf-8")
        assert f'revision: str = "{rev}"' in text
        assert f'down_revision: str = "{down}"' in text
        assert "Reversible: yes" in text


def test_seed_is_a_quality_pakistani_vocabulary() -> None:
    seed = _load_seed()
    careers: list[tuple[str, str, str, list[str]]] = seed._CAREERS
    assert len(careers) >= 45
    slugs = [c[0] for c in careers]
    assert len(slugs) == len(set(slugs))
    names = " ".join(c[1] for c in careers)
    for marker in ("CSS", "SUPARCO", "PMD", "MBBS"):
        assert marker in names
    assert len({c[2] for c in careers}) >= 8  # spans many sectors
    for _slug, _name, _sector, concepts in careers:
        assert concepts and all(isinstance(k, str) and k == k.lower() for k in concepts)


def test_seed_ids_are_deterministic_uuid5() -> None:
    seed = _load_seed()
    first = seed.career_id("civil-engineer")
    assert first == seed.career_id("civil-engineer")
    assert uuid.UUID(first).version == 5


# --- cache policy / config ------------------------------------------------------------


def _with_days(monkeypatch: pytest.MonkeyPatch, days: int) -> None:
    monkeypatch.setattr(
        cache, "get_settings", lambda: SimpleNamespace(CONCEPT_ENRICHMENT_CACHE_DAYS=days)
    )


def test_staleness_follows_configured_age(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    row = SchoolConceptApplication(
        concept_id="c",
        concept_label="C",
        status=ConceptApplicationStatus.READY,
        generated_at=now - timedelta(days=91),
    )
    _with_days(monkeypatch, 90)
    assert cache.is_stale(row, now) is True
    _with_days(monkeypatch, 120)
    assert cache.is_stale(row, now) is False


def test_non_ready_rows_are_never_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_days(monkeypatch, 1)
    row = SchoolConceptApplication(concept_id="c", concept_label="C")
    assert cache.is_stale(row) is False


def test_cache_days_setting_bounds() -> None:
    assert Settings().CONCEPT_ENRICHMENT_CACHE_DAYS == 90
    with pytest.raises(PydanticValidationError):
        Settings(CONCEPT_ENRICHMENT_CACHE_DAYS=0)
    with pytest.raises(PydanticValidationError):
        Settings(CONCEPT_ENRICHMENT_CACHE_DAYS=400)


def test_beat_entry_matches_arch_10_6() -> None:
    entry: Any = BEAT_SCHEDULE["refresh-concept-applications"]
    assert entry["task"] == "concept.refresh_quarterly"
    schedule = entry["schedule"]
    assert schedule.hour == {19} and schedule.minute == {30}


def test_refresh_task_registered_on_ml_queue() -> None:
    from app.features.concept_enrichment.tasks import refresh_quarterly

    assert refresh_quarterly.name == "concept.refresh_quarterly"
    assert refresh_quarterly.queue == "ml"


def test_enqueue_uses_named_task_on_ml_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.celery.celery_app import celery_app

    sent: list[tuple[Any, ...]] = []

    def _send_task(name: str, args: list[str], queue: str) -> None:
        sent.append((name, args, queue))

    monkeypatch.setattr(celery_app, "send_task", _send_task)
    cache.enqueue_enrichment("app-1")
    assert sent == [("concept.enrich_applications", ["app-1"], "ml")]


# --- real Postgres -----------------------------------------------------------------------


@requires_pg
async def test_careers_seed_applied(pg: AsyncSession) -> None:
    count = (await pg.execute(select(func.count()).select_from(Career))).scalar_one()
    assert count >= 45
    civil = (await pg.execute(select(Career).where(Career.slug == "civil-engineer"))).scalar_one()
    assert civil.id == _load_seed().career_id("civil-engineer")
    assert "forces" in civil.required_concepts


@requires_pg
async def test_one_cache_row_per_concept(pg: AsyncSession) -> None:
    pg.add(SchoolConceptApplication(concept_id="m15-test/forces", concept_label="Forces"))
    await pg.flush()
    with pytest.raises(IntegrityError):
        async with pg.begin_nested():
            pg.add(SchoolConceptApplication(concept_id="m15-test/forces", concept_label="Forces"))
            await pg.flush()


@requires_pg
async def test_simulation_state_is_isolated_per_student(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    pg.add(
        SchoolStudentSimulationProgress(
            student_user_id=seed.student_id, concept_id="forces", sim_state={"mass": 5}
        )
    )
    pg.add(
        SchoolStudentSimulationProgress(
            student_user_id=seed.other_student_id, concept_id="forces", sim_state={"mass": 9}
        )
    )
    await pg.flush()
    repo = SimulationProgressRepository(pg)
    mine = await repo.get_for_student(student_user_id=seed.student_id, concept_id="forces")
    theirs = await repo.get_for_student(student_user_id=seed.other_student_id, concept_id="forces")
    assert mine is not None and theirs is not None
    assert mine.sim_state == {"mass": 5} and theirs.sim_state == {"mass": 9}
    with pytest.raises(IntegrityError):
        async with pg.begin_nested():
            pg.add(
                SchoolStudentSimulationProgress(
                    student_user_id=seed.student_id, concept_id="forces", sim_state={}
                )
            )
            await pg.flush()


@requires_pg
async def test_refresh_sweep_picks_stale_failed_and_lost_only(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_days(monkeypatch, 90)
    now = datetime.now(timezone.utc)
    rows: dict[str, SchoolConceptApplication] = {
        "stale": SchoolConceptApplication(
            concept_id="m15/stale",
            concept_label="x",
            status=ConceptApplicationStatus.READY,
            generated_at=now - timedelta(days=100),
        ),
        "fresh": SchoolConceptApplication(
            concept_id="m15/fresh",
            concept_label="x",
            status=ConceptApplicationStatus.READY,
            generated_at=now - timedelta(days=10),
        ),
        "failed": SchoolConceptApplication(
            concept_id="m15/failed", concept_label="x", status=ConceptApplicationStatus.FAILED
        ),
        "lost": SchoolConceptApplication(
            concept_id="m15/lost",
            concept_label="x",
            status=ConceptApplicationStatus.PENDING,
            updated_at=now - timedelta(hours=3),
        ),
        "in_flight": SchoolConceptApplication(
            concept_id="m15/in-flight", concept_label="x", status=ConceptApplicationStatus.PENDING
        ),
    }
    pg.add_all(list(rows.values()))
    await pg.flush()
    enqueued: list[str] = []
    monkeypatch.setattr(cache, "enqueue_enrichment", enqueued.append)

    count = await cache.sweep_due_refreshes(pg, now=now)

    expected = {rows["stale"].id, rows["failed"].id, rows["lost"].id}
    picked = set(enqueued) & {r.id for r in rows.values()}
    assert picked == expected
    assert count >= 3
