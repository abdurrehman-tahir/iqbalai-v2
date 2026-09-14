"""Anonymized teacher benchmarking — T-139 (Flow 5 §3.11 #37).

School-tenant only (`SchoolTeacherBenchmark` has no independent counterpart —
no peer cohort within a one-person tenant, per the ticket). Weekly Celery
beat (`benchmark.update_weekly`, already locked in ARCH §10.6) computes each
teacher's percentile rank within their (subject, grade_range, region)
cohort, ranked by their average 7-dimension total score across authored
lecture versions.

**Grade bucketing is an assumption** — the spec names a `grade_range` column
but never defines its bucket boundaries. This uses the single
``Grade.level_ordinal`` (e.g. "9") the teacher's lecture was written for,
not a multi-grade span — flagged in the backlog notes, not silently picked.

**Opt-out is row-scoped, not a separate preference column** — no new
migration needed. ``POST .../benchmarks/opt-out`` bulk-flips
``opted_out=True`` (clearing percentile/cohort_size) on the teacher's
*existing* rows; the weekly beat then skips any row already marked
opted-out rather than overwriting it. A brand-new teacher with no rows yet
has nothing to opt out of until their first benchmark row exists — an
accepted, documented gap rather than a schema change to close it.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.teacher_coaching.benchmark_repository import SchoolTeacherBenchmarkRepository
from app.features.teacher_coaching.models import SchoolTeacherBenchmark

logger = structlog.get_logger(__name__)

# Below this, a "percentile" would functionally identify the one-or-two other
# teachers in the cohort — too small a crowd for genuine anonymity.
MIN_COHORT_SIZE = 3


async def compute_and_store_weekly_benchmarks(session: AsyncSession) -> dict[str, int]:
    """The `benchmark.update_weekly` beat's core work (ARCH §10.6)."""
    repo = SchoolTeacherBenchmarkRepository(session)
    scored_versions = await repo.list_scored_versions()

    # cohort_key -> {teacher_user_id: [total scores]}
    cohorts: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for scored in scored_versions:
        total = scored.scores_jsonb.get("total")
        if not isinstance(total, int | float):
            continue
        cohort_key = (scored.subject_id, scored.grade_level_ordinal, scored.region)
        cohorts[cohort_key][scored.teacher_user_id].append(float(total))

    existing_rows = await repo.list_all()
    opted_out_keys = {
        (row.teacher_user_id, row.subject_id, row.grade_range, row.region)
        for row in existing_rows
        if row.opted_out
    }
    by_key = {
        (row.teacher_user_id, row.subject_id, row.grade_range, row.region): row
        for row in existing_rows
    }

    cohorts_computed = 0
    teachers_updated = 0
    for (subject_id, grade_range, region), teacher_scores in cohorts.items():
        active = {
            teacher_id: statistics.mean(scores)
            for teacher_id, scores in teacher_scores.items()
            if (teacher_id, subject_id, grade_range, region) not in opted_out_keys
        }
        if len(active) < MIN_COHORT_SIZE:
            continue
        cohorts_computed += 1
        ranked = sorted(active.items(), key=lambda item: item[1])
        cohort_size = len(ranked)
        for rank, (teacher_id, _avg) in enumerate(ranked, start=1):
            # Percentile rank: how many peers this teacher scored at or above.
            percentile = round((rank / cohort_size) * 100)
            key = (teacher_id, subject_id, grade_range, region)
            row = by_key.get(key)
            if row is None:
                row = SchoolTeacherBenchmark(
                    teacher_user_id=teacher_id,
                    subject_id=subject_id,
                    grade_range=grade_range,
                    region=region,
                )
                repo.add(row)
            row.percentile = percentile
            row.cohort_size = cohort_size
            teachers_updated += 1

    await repo.commit()
    logger.info(
        "teacher_benchmarks_weekly_update_complete",
        cohorts_computed=cohorts_computed,
        teachers_updated=teachers_updated,
    )
    return {"cohorts_computed": cohorts_computed, "teachers_updated": teachers_updated}


async def get_teacher_benchmarks(
    session: AsyncSession, teacher_user_id: str
) -> list[dict[str, object]]:
    """Positively-framed benchmark rows for this teacher (Flow 5 §3.11 locked
    rule: "Top 23%", never "bottom 30%"). Opted-out / not-yet-computed rows
    (``percentile is None``) are excluded — nothing to show."""
    repo = SchoolTeacherBenchmarkRepository(session)
    rows = await repo.list_for_teacher_with_subject_name(teacher_user_id)
    out: list[dict[str, object]] = []
    for row, subject_name in rows:
        top_pct = max(1, 100 - (row.percentile or 0))
        out.append(
            {
                "id": row.id,
                "subject_name": subject_name,
                "grade_range": row.grade_range,
                "region": row.region,
                "top_percent": top_pct,
            }
        )
    return out


async def set_benchmark_opt_out(
    session: AsyncSession, *, teacher_user_id: str, opted_out: bool
) -> int:
    """Bulk-flips every existing benchmark row for this teacher. Returns the
    number of rows changed (0 if the teacher has none yet — see module
    docstring's documented bootstrapping gap)."""
    repo = SchoolTeacherBenchmarkRepository(session)
    rows = await repo.list_all_for_teacher(teacher_user_id)
    for row in rows:
        row.opted_out = opted_out
        if opted_out:
            row.percentile = None
            row.cohort_size = None
    if rows:
        await repo.commit()
    return len(rows)
