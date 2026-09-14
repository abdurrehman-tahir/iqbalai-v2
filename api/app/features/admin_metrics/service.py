"""Admin comparative teacher metrics — service layer (T-139, Flow 5 §3.11 #38).

Scope resolution mirrors ``app.features.schools.service`` (the existing
Platform/District/School precedent): Platform Admin sees every school,
District Admin their district's schools, School Admin only their own
(ARCH §6.19 ROLE_HIERARCHY). ``require_role("school_admin")`` on the route
is the floor — Coordinator and below never reach this service.

Results are cached in Redis for 1 hour, keyed by scope + filters — this is
a comparative dashboard, not a live feed; a school's cohort of scored
lecture versions does not change minute-to-minute.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import PermissionDeniedError
from app.features.admin_metrics.repository import AdminTeacherMetricsRepository, TeacherMetricsRow
from app.features.admin_metrics.schemas import TeacherMetricsRead
from app.infrastructure.cache.client import get_redis

logger = structlog.get_logger(__name__)

CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class MetricsFilters:
    subject_id: str | None = None
    grade_range: str | None = None
    school_id: str | None = None


def _cache_key(scope_school_ids: list[str] | None, filters: MetricsFilters) -> str:
    scope_part = "all" if scope_school_ids is None else ",".join(sorted(scope_school_ids))
    return (
        f"admin_metrics:teacher_metrics:{scope_part}:"
        f"{filters.subject_id or '-'}:{filters.grade_range or '-'}:{filters.school_id or '-'}"
    )


async def _resolve_scope_school_ids(
    session: AsyncSession, *, claims: dict[str, object], caller_role: str
) -> list[str] | None:
    """None means unrestricted (Platform Admin); otherwise the exact school IDs
    the caller may see."""
    if ROLE_HIERARCHY.get(caller_role, 0) >= ROLE_HIERARCHY["platform_admin"]:
        return None

    if ROLE_HIERARCHY.get(caller_role, 0) >= ROLE_HIERARCHY["district_admin"]:
        district_id = claims.get("district_id")
        if not district_id:
            raise PermissionDeniedError("District scope required")
        repo = AdminTeacherMetricsRepository(session)
        return await repo.list_school_ids_for_district(str(district_id))

    # school_admin floor (route dependency already rejects anything lower).
    school_id = claims.get("school_id")
    if not school_id:
        raise PermissionDeniedError("School scope required")
    return [str(school_id)]


def _aggregate(rows: list[TeacherMetricsRow]) -> list[TeacherMetricsRead]:
    groups: dict[tuple[str, str, str], list[TeacherMetricsRow]] = defaultdict(list)
    for row in rows:
        key = (row.teacher_user_id, row.subject_id, row.grade_level_ordinal)
        groups[key].append(row)

    def _dim_avg(group: list[TeacherMetricsRow], dim: str) -> float | None:
        values: list[float] = []
        for r in group:
            raw = r.scores_jsonb.get(dim)
            if isinstance(raw, int | float):
                values.append(float(raw))
        return round(statistics.mean(values), 1) if values else None

    out: list[TeacherMetricsRead] = []
    for (teacher_user_id, subject_id, grade_range), group in groups.items():
        first = group[0]
        topic_values = [r.topic_relevance_pct for r in group if r.topic_relevance_pct is not None]
        out.append(
            TeacherMetricsRead(
                teacher_user_id=teacher_user_id,
                teacher_name=first.teacher_name,
                school_id=first.school_id,
                school_name=first.school_name,
                subject_id=subject_id,
                subject_name=first.subject_name,
                grade_range=grade_range,
                lecture_count=len({r.lecture_id for r in group}),
                avg_originality=_dim_avg(group, "originality") or 0.0,
                avg_depth=_dim_avg(group, "depth") or 0.0,
                avg_cultural_relevance=_dim_avg(group, "cultural_relevance") or 0.0,
                avg_engagement=_dim_avg(group, "engagement") or 0.0,
                avg_alignment=_dim_avg(group, "alignment") or 0.0,
                avg_voice_quality=_dim_avg(group, "voice_quality"),
                avg_ai_learning=_dim_avg(group, "ai_learning") or 0.0,
                avg_total=_dim_avg(group, "total") or 0.0,
                avg_topic_relevance_pct=(
                    round(statistics.mean(topic_values), 1) if topic_values else None
                ),
            )
        )
    out.sort(key=lambda r: r.avg_total, reverse=True)
    return out


async def get_teacher_metrics(
    session: AsyncSession,
    *,
    claims: dict[str, object],
    caller_role: str,
    filters: MetricsFilters,
) -> list[TeacherMetricsRead]:
    scope_school_ids = await _resolve_scope_school_ids(
        session, claims=claims, caller_role=caller_role
    )
    if (
        filters.school_id is not None
        and scope_school_ids is not None
        and filters.school_id not in scope_school_ids
    ):
        raise PermissionDeniedError("School out of scope")

    cache_key = _cache_key(scope_school_ids, filters)
    redis = get_redis()
    cached = await redis.get(cache_key)
    if cached is not None:
        return [TeacherMetricsRead.model_validate(item) for item in json.loads(cached)]

    repo = AdminTeacherMetricsRepository(session)
    effective_school_ids = (
        [filters.school_id] if filters.school_id is not None else scope_school_ids
    )
    rows = await repo.list_scored_versions(school_ids=effective_school_ids)
    if filters.subject_id is not None:
        rows = [r for r in rows if r.subject_id == filters.subject_id]
    if filters.grade_range is not None:
        rows = [r for r in rows if r.grade_level_ordinal == filters.grade_range]

    result = _aggregate(rows)
    await redis.set(
        cache_key,
        json.dumps([item.model_dump(mode="json") for item in result]),
        ex=CACHE_TTL_SECONDS,
    )
    logger.info("admin_teacher_metrics_computed", rows=len(result), cache_key=cache_key)
    return result
