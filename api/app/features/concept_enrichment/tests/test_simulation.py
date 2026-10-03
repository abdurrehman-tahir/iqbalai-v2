"""T-191 — per-student mini-simulation state (flow-6 §3.10 / §5.9)."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationError, setup_exception_handlers
from app.features.concept_enrichment.models import (
    ConceptApplicationStatus,
    SchoolConceptApplication,
)
from app.features.concept_enrichment.repository import SimulationProgressRepository
from app.features.concept_enrichment.schemas import SimulationProgressRead
from app.features.concept_enrichment.simulation import SimulationProgressService
from app.features.student_highlights.tests.pg_support import Seed, requires_pg, seed_lecture
from app.features.users.models import User

SPEC: dict[str, Any] = {
    "title": "Push the cart",
    "scenario": "A cart on a road in Lahore.",
    "variables": [
        {
            "key": "mass",
            "label": "Mass",
            "unit": "kg",
            "min": 1,
            "max": 100,
            "step": 1,
            "default": 10,
        },
        {
            "key": "accel",
            "label": "Acceleration",
            "unit": "m/s²",
            "min": 0,
            "max": 10,
            "step": 0.5,
            "default": 2,
        },
    ],
    "output": {"label": "Force", "unit": "N", "expression": "mass * accel"},
}


async def _claims(pg: AsyncSession, user_id: str) -> dict[str, object]:
    user = await pg.get(User, user_id)
    assert user is not None
    return {"sub": user.authentik_id, "role": user.role.value}


def _svc(pg: AsyncSession) -> SimulationProgressService:
    svc = SimulationProgressService(pg)
    svc._enrichment._lecture_svc = MagicMock()
    svc._enrichment._lecture_svc.student_can_access_lecture = AsyncMock(return_value=True)
    return svc


async def _ready_concept(pg: AsyncSession, seed: Seed, *, sim: dict[str, Any] | None = SPEC) -> str:
    concepts = await _svc(pg)._enrichment.list_lecture_concepts(
        await _claims(pg, seed.student_id), seed.lecture_id
    )
    concept_id = concepts[0].concept_id
    pg.add(
        SchoolConceptApplication(
            concept_id=concept_id,
            concept_label="Forces",
            status=ConceptApplicationStatus.READY,
            generated_at=datetime.now(timezone.utc),
            mini_sim_prompt=sim,
        )
    )
    await pg.flush()
    return concept_id


@requires_pg
async def test_save_then_return_restores_state(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    concept = await _ready_concept(pg, seed)
    claims = await _claims(pg, seed.student_id)

    empty = await _svc(pg).get(claims, lecture_id=seed.lecture_id, concept_id=concept)
    assert empty.values == {} and empty.was_reset is False

    await _svc(pg).save(
        claims, lecture_id=seed.lecture_id, concept_id=concept, values={"mass": 40, "accel": 3.5}
    )
    restored = await _svc(pg).get(claims, lecture_id=seed.lecture_id, concept_id=concept)
    assert restored.values == {"mass": 40.0, "accel": 3.5}

    await _svc(pg).save(claims, lecture_id=seed.lecture_id, concept_id=concept, values={"mass": 7})
    again = await _svc(pg).get(claims, lecture_id=seed.lecture_id, concept_id=concept)
    assert again.values == {"mass": 7.0}  # upsert, single row


@requires_pg
async def test_state_is_per_student(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    concept = await _ready_concept(pg, seed)
    await _svc(pg).save(
        await _claims(pg, seed.student_id),
        lecture_id=seed.lecture_id,
        concept_id=concept,
        values={"mass": 99},
    )
    theirs = await _svc(pg).get(
        await _claims(pg, seed.other_student_id), lecture_id=seed.lecture_id, concept_id=concept
    )
    assert theirs.values == {}


@requires_pg
@pytest.mark.parametrize("values", [{"mass": 500}, {"gravity": 9.8}, {"mass": -1}])
async def test_out_of_spec_values_rejected(pg: AsyncSession, values: dict[str, float]) -> None:
    seed = await seed_lecture(pg)
    concept = await _ready_concept(pg, seed)
    with pytest.raises(ValidationError):
        await _svc(pg).save(
            await _claims(pg, seed.student_id),
            lecture_id=seed.lecture_id,
            concept_id=concept,
            values=values,
        )


@requires_pg
async def test_corrupted_state_is_reset_with_notice(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    concept = await _ready_concept(pg, seed)
    claims = await _claims(pg, seed.student_id)
    await _svc(pg).save(claims, lecture_id=seed.lecture_id, concept_id=concept, values={"mass": 5})
    row = await SimulationProgressRepository(pg).get_for_student(
        student_user_id=seed.student_id, concept_id=concept
    )
    assert row is not None
    row.sim_state = {"values": {"mass": "lots", "speed": 3}}
    await pg.flush()

    out = await _svc(pg).get(claims, lecture_id=seed.lecture_id, concept_id=concept)
    assert out.was_reset is True and out.values == {}
    assert row.sim_state == {}


@requires_pg
async def test_concept_without_sim_has_no_progress_endpoint(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    concept = await _ready_concept(pg, seed, sim=None)
    with pytest.raises(NotFoundError):
        await _svc(pg).get(
            await _claims(pg, seed.student_id), lecture_id=seed.lecture_id, concept_id=concept
        )


# --- API contract -----------------------------------------------------------------


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client() -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db

    async def _c() -> dict[str, object]:
        return {"sub": "auth-1", "role": "student"}

    app.dependency_overrides[get_current_user] = _c
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_simulation_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    read = SimulationProgressRead(concept_id="forces", values={"mass": 4.0})
    monkeypatch.setattr(SimulationProgressService, "get", AsyncMock(return_value=read))
    save = AsyncMock(return_value=read)
    monkeypatch.setattr(SimulationProgressService, "save", save)
    async with _client() as client:
        got = await client.get(
            "/api/v1/students/me/lectures/lec-1/simulation", params={"concept_id": "forces"}
        )
        put = await client.put(
            "/api/v1/students/me/lectures/lec-1/simulation",
            params={"concept_id": "forces"},
            json={"values": {"mass": 4}},
        )
        bad = await client.put(
            "/api/v1/students/me/lectures/lec-1/simulation",
            params={"concept_id": "forces"},
            json={"values": {"a": 1, "b": 2, "c": 3, "d": 4}},
        )
    assert got.status_code == 200 and put.status_code == 200
    SimulationProgressRead.model_validate(put.json()["data"])
    assert save.await_args is not None and save.await_args.kwargs["values"] == {"mass": 4.0}
    assert bad.status_code == 422
