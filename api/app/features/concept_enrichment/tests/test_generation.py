"""T-190 — concept enrichment generation (LLM mocked; flow-6 §3.10 / §5.9)."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError, setup_exception_handlers
from app.features.concept_enrichment import cache
from app.features.concept_enrichment import service as service_mod
from app.features.concept_enrichment.generation import (
    generate_enrichment,
    parse_output,
    safe_mini_sim,
)
from app.features.concept_enrichment.models import (
    Career,
    ConceptApplicationStatus,
    SchoolConceptApplication,
)
from app.features.concept_enrichment.schemas import ConceptEnrichmentRead, LectureConceptRead
from app.features.concept_enrichment.service import ConceptEnrichmentService, concept_label
from app.features.concept_enrichment.sim_expression import ExpressionError, evaluate, validate
from app.features.student_highlights.tests.pg_support import make_user, requires_pg, seed_lecture
from app.features.users.models import User, UserRole
from app.infrastructure.llm import client as llm_client
from app.infrastructure.llm.client import ChatUsage
from app.infrastructure.llm.prompts.concept_enrichment_v1 import (
    PROMPT_VERSION,
    CareerOption,
    ConceptEnrichmentInput,
    MiniSimOut,
    render,
)

# --- safe expression ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "values", "expected"),
    [
        ("mass * acceleration", {"mass": 10, "acceleration": 2}, 20.0),
        ("a + b * c", {"a": 1, "b": 2, "c": 3}, 7.0),
        ("(a + b) * c", {"a": 1, "b": 2, "c": 3}, 9.0),
        ("2 ^ 3 ^ 2", {}, 512.0),  # right-associative
        ("-a + 4", {"a": 1}, 3.0),
        ("0.5 * m * v ^ 2", {"m": 2, "v": 3}, 9.0),
    ],
)
def test_expression_evaluates(expr: str, values: dict[str, float], expected: float) -> None:
    assert evaluate(expr, values) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os')",
        "a.__class__",
        "open('x')",
        "a ** b",
        "a; b",
        "a +",
        "(a",
        "unknown * 2",
        "",
        "a" + " + a" * 40,
    ],
)
def test_expression_rejects_unsafe_or_invalid(expr: str) -> None:
    with pytest.raises(ExpressionError):
        evaluate(expr, {"a": 1, "b": 2})


def test_division_by_zero_is_undefined_not_an_error() -> None:
    assert evaluate("a / b", {"a": 1, "b": 0}) is None
    assert validate("a / b", {"a", "b"}, {"a": 1, "b": 0}) is False


# --- prompt / parsing ------------------------------------------------------------------


def test_prompt_lists_vocabulary_ids_and_is_versioned() -> None:
    call = render(
        ConceptEnrichmentInput(
            concept_label="Newton's second law",
            careers=[CareerOption(id="c-1", name="Civil Engineer", sector="Engineering")],
        )
    )
    assert call.version == PROMPT_VERSION == "concept_enrichment.v1"
    assert "c-1 | Civil Engineer" in call.user
    assert "Never invent" in call.system


def _sim(**overrides: Any) -> dict[str, Any]:
    sim: dict[str, Any] = {
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
    sim.update(overrides)
    return sim


def _llm_json(career_ids: list[str], sim: dict[str, Any] | None) -> str:
    return (
        "```json\n"
        + json.dumps(
            {
                "real_world_uses": [
                    {"title": "Rickshaws", "description": "Heavier loads need more force."},
                    {"title": "Cricket", "description": "A bat changes the ball's momentum."},
                ],
                "career_ids": career_ids,
                "mini_sim": sim,
            }
        )
        + "\n```"
    )


def test_parse_output_strips_fences() -> None:
    out = parse_output(_llm_json(["x"], _sim()))
    assert len(out.real_world_uses) == 2 and out.career_ids == ["x"]


def test_safe_mini_sim_accepts_valid_spec() -> None:
    spec = safe_mini_sim(MiniSimOut.model_validate(_sim()))
    assert spec is not None and spec["output"]["expression"] == "mass * accel"


@pytest.mark.parametrize(
    "bad",
    [
        {"output": {"label": "F", "unit": "N", "expression": "mass * gravity"}},  # unknown var
        {
            "output": {"label": "F", "unit": "N", "expression": "mass / (accel - 2)"}
        },  # ÷0 at default
        {
            "variables": [
                {
                    "key": "mass",
                    "label": "M",
                    "unit": "",
                    "min": 5,
                    "max": 1,
                    "step": 1,
                    "default": 3,
                }
            ],
            "output": {"label": "F", "unit": "", "expression": "mass"},
        },  # min > max
    ],
)
def test_safe_mini_sim_degrades_invalid_spec_to_text_only(bad: dict[str, Any]) -> None:
    assert safe_mini_sim(MiniSimOut.model_validate(_sim(**bad))) is None


def test_concept_label_prefers_metadata_then_path_segment() -> None:
    assert concept_label("x/y", {"sub_topic": "Inertia"}, "Forces") == "Inertia"
    assert concept_label("physics/forces/newton-2", {}, "Forces") == "newton-2"
    assert concept_label("", {}, "Forces") == "Forces"


def test_enrich_task_registered() -> None:
    from app.features.concept_enrichment.tasks import enrich_applications

    assert enrich_applications.name == "concept.enrich_applications"
    assert enrich_applications.queue == "ml"


# --- generation (real Postgres, LLM mocked) ----------------------------------------------


async def _careers(pg: AsyncSession) -> list[Career]:
    return list((await pg.execute(select(Career).order_by(Career.slug).limit(3))).scalars().all())


def _mock_llm(
    monkeypatch: pytest.MonkeyPatch, text: str, tokens: tuple[int, int] = (900, 300)
) -> AsyncMock:
    mock = AsyncMock(
        return_value=ChatUsage(text=text, prompt_tokens=tokens[0], completion_tokens=tokens[1])
    )
    monkeypatch.setattr(llm_client, "chat_with_usage", mock)
    return mock


async def _pending(
    pg: AsyncSession, concept_id: str = "m15-gen/forces"
) -> SchoolConceptApplication:
    row = SchoolConceptApplication(concept_id=concept_id, concept_label="Newton's second law")
    pg.add(row)
    await pg.flush()
    return row


@requires_pg
async def test_cache_miss_generation_persists_and_filters_careers(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    careers = await _careers(pg)
    llm = _mock_llm(
        monkeypatch, _llm_json([careers[0].id, "free-text-astronaut", careers[1].id], _sim())
    )
    row = await _pending(pg)

    with structlog.testing.capture_logs() as logs:
        outcome = await generate_enrichment(pg, row.id)

    assert outcome == "ready"
    llm.assert_awaited_once()
    assert llm.await_args is not None and llm.await_args.kwargs["task"] == "concept_enrichment"
    assert row.status == ConceptApplicationStatus.READY
    assert row.career_link_ids == [careers[0].id, careers[1].id]  # unknown id dropped
    assert len(row.real_world_uses) == 2
    assert row.mini_sim_prompt is not None
    assert row.generated_at is not None
    assert row.prompt_version == "concept_enrichment.v1"
    # 1200 tokens × $0.001/1k (default)
    assert row.regen_cost_usd == Decimal("0.0012")
    event = next(e for e in logs if e["event"] == "concept_enrichment_generated")
    assert event["cost_usd"] == "0.0012"
    assert event["careers_dropped_not_in_vocabulary"] == 1


@requires_pg
async def test_fresh_row_is_never_regenerated(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _mock_llm(monkeypatch, _llm_json([], None))
    row = await _pending(pg)
    row.status = ConceptApplicationStatus.READY
    row.generated_at = datetime.now(timezone.utc)
    await pg.flush()
    assert await generate_enrichment(pg, row.id) == "skipped_fresh"
    llm.assert_not_awaited()


@requires_pg
async def test_first_generation_failure_marks_failed(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_llm(monkeypatch, "not json at all")
    row = await _pending(pg)
    assert await generate_enrichment(pg, row.id) == "failed"
    assert row.status == ConceptApplicationStatus.FAILED


@requires_pg
async def test_failed_refresh_keeps_existing_content(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        llm_client, "chat_with_usage", AsyncMock(side_effect=TimeoutError("llm down"))
    )
    row = await _pending(pg)
    row.status = ConceptApplicationStatus.READY
    row.generated_at = datetime.now(timezone.utc) - timedelta(days=400)
    row.real_world_uses = [{"title": "Old", "description": "Still valid"}]
    await pg.commit()
    row_id = row.id  # the generator rolls back → ``row`` is expired afterwards

    assert await generate_enrichment(pg, row_id) == "refresh_failed_kept_ready"
    refreshed = await pg.get(SchoolConceptApplication, row_id, populate_existing=True)
    assert refreshed is not None
    assert refreshed.status == ConceptApplicationStatus.READY
    assert refreshed.real_world_uses == [{"title": "Old", "description": "Still valid"}]


@requires_pg
async def test_invalid_sim_degrades_to_text_only(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _sim(output={"label": "F", "unit": "N", "expression": "__import__('os')"})
    _mock_llm(monkeypatch, _llm_json([], bad))
    row = await _pending(pg)
    assert await generate_enrichment(pg, row.id) == "ready"
    assert row.mini_sim_prompt is None
    assert len(row.real_world_uses) == 2


# --- service (real Postgres): hit / miss / per-concept reuse ------------------------------


async def _claims(pg: AsyncSession, user_id: str) -> dict[str, object]:
    user = await pg.get(User, user_id)
    assert user is not None
    return {"sub": user.authentik_id, "role": user.role.value}


def _svc(pg: AsyncSession, *, can_access: bool = True) -> ConceptEnrichmentService:
    svc = ConceptEnrichmentService(pg)
    svc._lecture_svc = MagicMock()
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=can_access)
    return svc


@requires_pg
async def test_miss_then_hit_shared_across_students(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    enqueued: list[str] = []
    monkeypatch.setattr(service_mod, "enqueue_enrichment", enqueued.append)
    concepts = await _svc(pg).list_lecture_concepts(
        await _claims(pg, seed.student_id), seed.lecture_id
    )
    concept_id = concepts[0].concept_id

    first = await _svc(pg).get_enrichment(
        await _claims(pg, seed.student_id), lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert first.status == "pending" and len(enqueued) == 1

    # Repeat request while pending → no second enqueue.
    await _svc(pg).get_enrichment(
        await _claims(pg, seed.student_id), lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert len(enqueued) == 1

    # The worker generates it (LLM mocked)…
    careers = await _careers(pg)
    llm = _mock_llm(monkeypatch, _llm_json([careers[0].id], _sim()))
    assert await generate_enrichment(pg, enqueued[0]) == "ready"
    llm.assert_awaited_once()

    # …and a SECOND student gets the cached row: no enqueue, no LLM call.
    second = await _svc(pg).get_enrichment(
        await _claims(pg, seed.other_student_id), lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert second.status == "ready"
    assert second.careers[0].id == careers[0].id
    assert second.mini_sim is not None and second.mini_sim.output.expression == "mass * accel"
    assert len(enqueued) == 1
    llm.assert_awaited_once()
    rows = (
        await pg.execute(
            select(func.count())
            .select_from(SchoolConceptApplication)
            .where(SchoolConceptApplication.concept_id == concept_id)
        )
    ).scalar_one()
    assert rows == 1  # one cache row per concept, not per student


@requires_pg
async def test_stale_entry_served_while_refresh_enqueued(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    concepts = await _svc(pg).list_lecture_concepts(
        await _claims(pg, seed.student_id), seed.lecture_id
    )
    old = datetime.now(timezone.utc) - timedelta(days=200)
    pg.add(
        SchoolConceptApplication(
            concept_id=concepts[0].concept_id,
            concept_label="Forces",
            status=ConceptApplicationStatus.READY,
            generated_at=old,
            updated_at=old,
            real_world_uses=[{"title": "Old", "description": "content"}],
        )
    )
    await pg.flush()
    enqueued: list[str] = []
    monkeypatch.setattr(service_mod, "enqueue_enrichment", enqueued.append)
    monkeypatch.setattr(cache, "get_settings", lambda: MagicMock(CONCEPT_ENRICHMENT_CACHE_DAYS=90))

    out = await _svc(pg).get_enrichment(
        await _claims(pg, seed.student_id),
        lecture_id=seed.lecture_id,
        concept_id=concepts[0].concept_id,
    )
    assert out.status == "ready" and out.refreshing is True
    assert out.real_world_uses[0].title == "Old"
    assert len(enqueued) == 1


@requires_pg
async def test_concept_not_in_lecture_is_404_and_never_generated(
    pg: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg)
    enqueued: list[str] = []
    monkeypatch.setattr(service_mod, "enqueue_enrichment", enqueued.append)
    with pytest.raises(NotFoundError):
        await _svc(pg).get_enrichment(
            await _claims(pg, seed.student_id),
            lecture_id=seed.lecture_id,
            concept_id="quantum-chromodynamics",
        )
    assert enqueued == []


@requires_pg
async def test_student_without_lecture_access_is_denied(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    outsider = await make_user(pg, role=UserRole.STUDENT, school_id=None)
    with pytest.raises(PermissionDeniedError):
        await _svc(pg, can_access=False).list_lecture_concepts(
            await _claims(pg, outsider.id), seed.lecture_id
        )


# --- API contract ---------------------------------------------------------------------------


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client(role: str) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db

    async def _c() -> dict[str, object]:
        return {"sub": "auth-1", "role": role}

    app.dependency_overrides[get_current_user] = _c
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_concepts_and_enrichment_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ConceptEnrichmentService,
        "list_lecture_concepts",
        AsyncMock(
            return_value=[
                LectureConceptRead(
                    concept_id="physics/forces",
                    label="forces",
                    first_paragraph_id="p1",
                    first_paragraph_ordinal=0,
                )
            ]
        ),
    )
    get_mock = AsyncMock(
        return_value=ConceptEnrichmentRead(
            concept_id="physics/forces", concept_label="forces", status="pending"
        )
    )
    monkeypatch.setattr(ConceptEnrichmentService, "get_enrichment", get_mock)
    async with _client("student") as client:
        concepts = await client.get("/api/v1/students/me/lectures/lec-1/concepts")
        enrichment = await client.get(
            "/api/v1/students/me/lectures/lec-1/enrichment",
            params={"concept_id": "physics/forces"},
        )
        missing = await client.get("/api/v1/students/me/lectures/lec-1/enrichment")
    assert concepts.status_code == 200
    LectureConceptRead.model_validate(concepts.json()["data"][0])
    assert enrichment.status_code == 200
    ConceptEnrichmentRead.model_validate(enrichment.json()["data"])
    assert get_mock.await_args is not None
    assert get_mock.await_args.kwargs["concept_id"] == "physics/forces"  # slash survives
    assert missing.status_code == 422
