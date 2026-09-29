"""Upsert helpers for session_difficulty_log (T-175 / T-176 / T-182)."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.session_difficulty.angles import TEACHING_ANGLES, next_angle
from app.features.session_difficulty.models import (
    DifficultyTenantType,
    IndependentSessionDifficultyLog,
    SchoolSessionDifficultyLog,
)


def _is_independent(tenant_type: str) -> bool:
    return tenant_type.lower() == DifficultyTenantType.INDEPENDENT.value


async def get_or_create_log(
    session: AsyncSession,
    *,
    session_id: str,
    sub_topic_id: str,
    tenant_type: str = "school",
) -> SchoolSessionDifficultyLog | IndependentSessionDifficultyLog:
    if _is_independent(tenant_type):
        ind_stmt = select(IndependentSessionDifficultyLog).where(
            IndependentSessionDifficultyLog.session_id == session_id,
            IndependentSessionDifficultyLog.sub_topic_id == sub_topic_id,
        )
        ind_row = (await session.execute(ind_stmt)).scalar_one_or_none()
        if ind_row is None:
            ind_row = IndependentSessionDifficultyLog(
                session_id=session_id,
                sub_topic_id=sub_topic_id,
                tenant_type=DifficultyTenantType.INDEPENDENT,
            )
            session.add(ind_row)
            await session.flush()
        return ind_row

    school_stmt = select(SchoolSessionDifficultyLog).where(
        SchoolSessionDifficultyLog.session_id == session_id,
        SchoolSessionDifficultyLog.sub_topic_id == sub_topic_id,
    )
    school_row = (await session.execute(school_stmt)).scalar_one_or_none()
    if school_row is None:
        school_row = SchoolSessionDifficultyLog(
            session_id=session_id,
            sub_topic_id=sub_topic_id,
            tenant_type=DifficultyTenantType.SCHOOL,
        )
        session.add(school_row)
        await session.flush()
    return school_row


async def increment_question_count(
    session: AsyncSession,
    *,
    session_id: str,
    sub_topic_id: str,
    tenant_type: str = "school",
) -> SchoolSessionDifficultyLog | IndependentSessionDifficultyLog:
    """Increment question_count for (session, sub_topic)."""
    row = await get_or_create_log(
        session,
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        tenant_type=tenant_type,
    )
    row.question_count = int(row.question_count or 0) + 1
    await session.flush()
    return row


async def assign_next_angle(
    session: AsyncSession,
    *,
    session_id: str,
    sub_topic_id: str,
    tenant_type: str = "school",
) -> tuple[SchoolSessionDifficultyLog | IndependentSessionDifficultyLog, str]:
    """Assign next unused teaching angle without changing question_count."""
    row = await get_or_create_log(
        session,
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        tenant_type=tenant_type,
    )
    tried = [str(a) for a in (row.tried_angles or [])]
    # Full cycle → reset so angles can rotate again.
    if all(a in tried for a in TEACHING_ANGLES):
        tried = []
    angle = next_angle(tried)
    if angle not in tried:
        tried.append(angle)
    row.tried_angles = cast(list[object], tried)
    row.last_angle = angle
    await session.flush()
    return row, angle


async def get_log(
    session: AsyncSession,
    *,
    session_id: str,
    sub_topic_id: str,
    tenant_type: str = "school",
) -> SchoolSessionDifficultyLog | IndependentSessionDifficultyLog | None:
    if _is_independent(tenant_type):
        ind_stmt = select(IndependentSessionDifficultyLog).where(
            IndependentSessionDifficultyLog.session_id == session_id,
            IndependentSessionDifficultyLog.sub_topic_id == sub_topic_id,
        )
        return (await session.execute(ind_stmt)).scalar_one_or_none()
    school_stmt = select(SchoolSessionDifficultyLog).where(
        SchoolSessionDifficultyLog.session_id == session_id,
        SchoolSessionDifficultyLog.sub_topic_id == sub_topic_id,
    )
    return (await session.execute(school_stmt)).scalar_one_or_none()


def log_as_dict(
    row: SchoolSessionDifficultyLog | IndependentSessionDifficultyLog,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "sub_topic_id": row.sub_topic_id,
        "question_count": row.question_count,
        "tried_angles": list(row.tried_angles or []),
        "last_angle": row.last_angle,
        "tenant_type": row.tenant_type.value
        if hasattr(row.tenant_type, "value")
        else str(row.tenant_type),
    }
