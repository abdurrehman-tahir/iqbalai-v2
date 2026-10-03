"""Per-session teaching-angle adaptation for lecture Q&A (T-182).

STYLE = Custom Persona (``infrastructure/llm/persona.py``).
STRATEGY = this module. Both prepend; persona is never overwritten.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.features.session_difficulty.angles import adaptation_context_block
from app.features.session_difficulty.repository import assign_next_angle, get_log
from app.features.session_difficulty.subtopic import resolve_sub_topic_id

logger = structlog.get_logger(__name__)


async def resolve_adaptation_block(
    session: AsyncSession,
    *,
    session_id: str | None,
    source_chunk_id: str | None,
    lecture_id: str | None = None,
    paragraph_id: str | None = None,
    tenant_type: str = "school",
) -> str | None:
    """Return adaptation STRATEGY text when threshold is met; else None."""
    if not session_id:
        return None

    settings = get_settings()
    threshold = int(settings.AI_ADAPT_QUESTION_THRESHOLD)
    sub_topic_id = await resolve_sub_topic_id(
        session,
        source_chunk_id=source_chunk_id,
        lecture_id=lecture_id,
        paragraph_id=paragraph_id,
    )
    if not sub_topic_id:
        return None

    row = await get_log(
        session,
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        tenant_type=tenant_type,
    )
    count = int(row.question_count) if row is not None else 0
    if count < threshold:
        return None

    # Reuse last_angle if already assigned for this count pass; else assign.
    if row is not None and row.last_angle and len(row.tried_angles or []) >= 1:
        # Assign a fresh angle only when question_count increased past last assign.
        # Heuristic: if tried_angles length < (count - threshold + 1), assign again.
        needed = max(1, count - threshold + 1)
        if len(list(row.tried_angles or [])) < needed:
            row, angle = await assign_next_angle(
                session,
                session_id=session_id,
                sub_topic_id=sub_topic_id,
                tenant_type=tenant_type,
            )
        else:
            angle = str(row.last_angle)
    else:
        row, angle = await assign_next_angle(
            session,
            session_id=session_id,
            sub_topic_id=sub_topic_id,
            tenant_type=tenant_type,
        )

    block = adaptation_context_block(angle=angle, question_count=count)
    logger.info(
        "session_adaptation_applied",
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        angle=angle,
        question_count=count,
    )
    return block


def prepend_adaptation(adaptation_block: str | None, system_prompt: str) -> str:
    """Compose STRATEGY ahead of (persona-prepended) system prompt."""
    if not adaptation_block or not adaptation_block.strip():
        return system_prompt
    system = system_prompt.strip()
    block = adaptation_block.strip()
    if not system:
        return block
    return f"{block}\n\n{system}"


async def adaptation_state_for_tests(
    session: AsyncSession,
    *,
    session_id: str,
    sub_topic_id: str,
    tenant_type: str = "school",
) -> dict[str, Any] | None:
    row = await get_log(
        session,
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        tenant_type=tenant_type,
    )
    if row is None:
        return None
    return {
        "question_count": row.question_count,
        "tried_angles": list(row.tried_angles or []),
        "last_angle": row.last_angle,
    }
