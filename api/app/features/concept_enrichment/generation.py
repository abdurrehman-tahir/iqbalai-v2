"""Concept enrichment generation — T-190 (flow-6 §3.10, #71).

Runs inside the ``concept.enrich_applications`` Celery task. One LLM call per
concept (typed prompt ``concept_enrichment_v1`` through the LLM chokepoint),
then:

- career ids are intersected with the ``careers`` vocabulary (unknown ids are
  dropped — the model can never create a free-text career link);
- the mini-sim spec is validated against the safe expression grammar; an
  invalid spec degrades to text-only (§5.9) instead of failing the concept;
- cost is estimated from token usage, logged, and stored on the row.

Concurrency: the row is locked ``FOR UPDATE SKIP LOCKED`` — a second worker
picking up the same concept skips instead of paying for a duplicate call.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.features.concept_enrichment.cache import is_stale
from app.features.concept_enrichment.models import (
    ConceptApplicationStatus,
    SchoolConceptApplication,
)
from app.features.concept_enrichment.repository import CareerRepository
from app.features.concept_enrichment.sim_expression import validate
from app.infrastructure.llm import client as llm
from app.infrastructure.llm.prompts.concept_enrichment_v1 import (
    PROMPT_VERSION,
    CareerOption,
    ConceptEnrichmentInput,
    ConceptEnrichmentOutput,
    MiniSimOut,
    render,
)

logger = structlog.get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
LLM_TASK = "concept_enrichment"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_output(raw: str) -> ConceptEnrichmentOutput:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return ConceptEnrichmentOutput.model_validate(cast(dict[str, Any], json.loads(text)))


def safe_mini_sim(sim: MiniSimOut | None) -> dict[str, Any] | None:
    """Keep the spec only if every variable is sane and the expression is safe."""
    if sim is None:
        return None
    keys = [v.key for v in sim.variables]
    if len(set(keys)) != len(keys):
        return None
    for v in sim.variables:
        if not (v.min < v.max and v.min <= v.default <= v.max and v.step <= v.max - v.min):
            return None
    defaults = {v.key: v.default for v in sim.variables}
    if not validate(sim.output.expression, set(keys), defaults):
        return None
    return sim.model_dump(mode="json")


def estimate_cost(total_tokens: int) -> Decimal:
    per_1k = Decimal(str(get_settings().CONCEPT_ENRICHMENT_USD_PER_1K_TOKENS))
    return (Decimal(total_tokens) / Decimal(1000) * per_1k).quantize(Decimal("0.0001"))


async def _lock_row(session: AsyncSession, application_id: str) -> SchoolConceptApplication | None:
    result = await session.execute(
        select(SchoolConceptApplication)
        .where(SchoolConceptApplication.id == application_id)
        .with_for_update(skip_locked=True)
    )
    return result.scalars().first()


async def generate_enrichment(session: AsyncSession, application_id: str) -> str:
    """Generate + persist one concept's enrichment. Returns an outcome tag."""
    row = await _lock_row(session, application_id)
    if row is None:
        return "skipped_locked_or_missing"
    if row.status == ConceptApplicationStatus.READY and not is_stale(row):
        # Already fresh (e.g. duplicate enqueue): never pay for a second call.
        await session.rollback()
        return "skipped_fresh"

    was_ready = row.status == ConceptApplicationStatus.READY
    careers = await CareerRepository(session).list_all()
    prompt = render(
        ConceptEnrichmentInput(
            concept_label=row.concept_label,
            careers=[CareerOption(id=c.id, name=c.name, sector=c.sector) for c in careers],
        )
    )
    try:
        usage = await llm.chat_with_usage(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task=LLM_TASK,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        output = parse_output(usage.text)
    except (ValidationError, ValueError) as exc:
        return await _record_failure(session, row, was_ready, f"invalid output: {exc}")
    except Exception as exc:  # provider/network failure — retried by the daily sweep
        return await _record_failure(session, row, was_ready, f"llm error: {exc}")

    vocabulary = {c.id for c in careers}
    career_ids = [cid for cid in dict.fromkeys(output.career_ids) if cid in vocabulary]
    dropped = len(output.career_ids) - len(career_ids)
    cost = estimate_cost(usage.total_tokens)

    row.real_world_uses = [u.model_dump(mode="json") for u in output.real_world_uses]
    row.career_link_ids = career_ids
    row.mini_sim_prompt = safe_mini_sim(output.mini_sim)
    row.status = ConceptApplicationStatus.READY
    row.generated_at = _utcnow()
    row.regen_cost_usd = cost
    row.prompt_version = PROMPT_VERSION
    await session.commit()

    logger.info(
        "concept_enrichment_generated",
        concept_application_id=row.id,
        concept_id=row.concept_id,
        prompt_version=PROMPT_VERSION,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        cost_usd=str(cost),
        careers_linked=len(career_ids),
        careers_dropped_not_in_vocabulary=dropped,
        mini_sim=row.mini_sim_prompt is not None,
        refresh=was_ready,
    )
    return "ready"


async def _record_failure(
    session: AsyncSession, row: SchoolConceptApplication, was_ready: bool, reason: str
) -> str:
    """First generation → FAILED. A failed *refresh* keeps the existing READY
    content (students keep their enrichment; the sweep retries tomorrow)."""
    logger.warning(
        "concept_enrichment_failed",
        concept_application_id=row.id,
        concept_id=row.concept_id,
        refresh=was_ready,
        reason=reason[:300],
    )
    if was_ready:
        await session.rollback()
        return "refresh_failed_kept_ready"
    row.status = ConceptApplicationStatus.FAILED
    await session.commit()
    return "failed"
