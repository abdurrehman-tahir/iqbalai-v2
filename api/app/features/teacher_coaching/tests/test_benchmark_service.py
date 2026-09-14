"""T-139 — anonymized teacher benchmarking service (Flow 5 §3.11 #37)."""

from __future__ import annotations

from typing import Any

import pytest

from app.features.teacher_coaching import benchmark_service
from app.features.teacher_coaching.benchmark_repository import ScoredVersionRow
from app.features.teacher_coaching.models import SchoolTeacherBenchmark


class _FakeRepo:
    scored_versions: list[ScoredVersionRow] = []
    existing: list[SchoolTeacherBenchmark] = []
    added: list[SchoolTeacherBenchmark] = []
    committed = False

    def __init__(self, session: Any) -> None:
        pass

    async def list_scored_versions(self) -> list[ScoredVersionRow]:
        return list(self.scored_versions)

    async def list_all(self) -> list[SchoolTeacherBenchmark]:
        return list(self.existing)

    async def list_for_teacher_with_subject_name(
        self, teacher_user_id: str
    ) -> list[tuple[SchoolTeacherBenchmark, str]]:
        return [
            (row, "Mathematics")
            for row in self.existing
            if row.teacher_user_id == teacher_user_id
            and not row.opted_out
            and row.percentile is not None
        ]

    async def list_all_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherBenchmark]:
        return [row for row in self.existing if row.teacher_user_id == teacher_user_id]

    def add(self, row: SchoolTeacherBenchmark) -> None:
        self.added.append(row)
        self.existing.append(row)

    async def commit(self) -> None:
        type(self).committed = True


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.scored_versions = []
    _FakeRepo.existing = []
    _FakeRepo.added = []
    _FakeRepo.committed = False
    monkeypatch.setattr(
        "app.features.teacher_coaching.benchmark_service.SchoolTeacherBenchmarkRepository",
        _FakeRepo,
    )


def _scored(teacher: str, total: float, *, subject: str = "subj-1") -> ScoredVersionRow:
    return ScoredVersionRow(
        teacher_user_id=teacher,
        subject_id=subject,
        grade_level_ordinal="9",
        region="Punjab",
        scores_jsonb={"total": total},
    )


@pytest.mark.asyncio
async def test_cohort_below_min_size_is_skipped() -> None:
    _FakeRepo.scored_versions = [_scored("t-1", 80.0), _scored("t-2", 60.0)]

    result = await benchmark_service.compute_and_store_weekly_benchmarks(None)  # type: ignore[arg-type]

    assert result == {"cohorts_computed": 0, "teachers_updated": 0}
    assert _FakeRepo.added == []


@pytest.mark.asyncio
async def test_cohort_at_min_size_computes_percentiles() -> None:
    _FakeRepo.scored_versions = [
        _scored("t-1", 90.0),
        _scored("t-2", 60.0),
        _scored("t-3", 30.0),
    ]

    result = await benchmark_service.compute_and_store_weekly_benchmarks(None)  # type: ignore[arg-type]

    assert result == {"cohorts_computed": 1, "teachers_updated": 3}
    by_teacher = {row.teacher_user_id: row for row in _FakeRepo.added}
    assert by_teacher["t-3"].percentile == 33  # lowest scorer -> lowest rank/percentile
    assert by_teacher["t-1"].percentile == 100  # highest scorer -> top percentile
    assert all(row.cohort_size == 3 for row in _FakeRepo.added)
    assert _FakeRepo.committed


@pytest.mark.asyncio
async def test_multiple_lecture_versions_average_per_teacher() -> None:
    _FakeRepo.scored_versions = [
        _scored("t-1", 90.0),
        _scored("t-1", 70.0),  # averages to 80
        _scored("t-2", 60.0),
        _scored("t-3", 30.0),
    ]

    await benchmark_service.compute_and_store_weekly_benchmarks(None)  # type: ignore[arg-type]

    by_teacher = {row.teacher_user_id: row for row in _FakeRepo.added}
    assert by_teacher["t-1"].percentile == 100


@pytest.mark.asyncio
async def test_opted_out_teacher_excluded_from_cohort_and_not_overwritten() -> None:
    opted_out_row = SchoolTeacherBenchmark(
        teacher_user_id="t-1",
        subject_id="subj-1",
        grade_range="9",
        region="Punjab",
        percentile=None,
        cohort_size=None,
        opted_out=True,
    )
    _FakeRepo.existing = [opted_out_row]
    _FakeRepo.scored_versions = [
        _scored("t-1", 95.0),  # opted out — excluded from ranking
        _scored("t-2", 60.0),
        _scored("t-3", 30.0),
    ]

    result = await benchmark_service.compute_and_store_weekly_benchmarks(None)  # type: ignore[arg-type]

    # Only 2 active teachers remain once t-1 is excluded — below MIN_COHORT_SIZE.
    assert result == {"cohorts_computed": 0, "teachers_updated": 0}
    assert opted_out_row.percentile is None


@pytest.mark.asyncio
async def test_non_numeric_total_is_skipped() -> None:
    row = ScoredVersionRow(
        teacher_user_id="t-1",
        subject_id="subj-1",
        grade_level_ordinal="9",
        region="Punjab",
        scores_jsonb={"total": "not-a-number"},
    )
    _FakeRepo.scored_versions = [row, _scored("t-2", 50.0), _scored("t-3", 40.0)]

    result = await benchmark_service.compute_and_store_weekly_benchmarks(None)  # type: ignore[arg-type]

    assert result == {"cohorts_computed": 0, "teachers_updated": 0}


@pytest.mark.asyncio
async def test_get_teacher_benchmarks_returns_positively_framed_top_percent() -> None:
    row = SchoolTeacherBenchmark(
        teacher_user_id="t-1",
        subject_id="subj-1",
        grade_range="9",
        region="Punjab",
        percentile=77,
        cohort_size=10,
    )
    _FakeRepo.existing = [row]

    out = await benchmark_service.get_teacher_benchmarks(None, "t-1")  # type: ignore[arg-type]

    assert out == [
        {
            "id": row.id,
            "subject_name": "Mathematics",
            "grade_range": "9",
            "region": "Punjab",
            "top_percent": 23,
        }
    ]


@pytest.mark.asyncio
async def test_get_teacher_benchmarks_excludes_opted_out_and_uncomputed() -> None:
    opted_out = SchoolTeacherBenchmark(
        teacher_user_id="t-1",
        subject_id="subj-1",
        grade_range="9",
        region="Punjab",
        percentile=50,
        cohort_size=5,
        opted_out=True,
    )
    uncomputed = SchoolTeacherBenchmark(
        teacher_user_id="t-1",
        subject_id="subj-2",
        grade_range="9",
        region="Punjab",
        percentile=None,
        cohort_size=None,
    )
    _FakeRepo.existing = [opted_out, uncomputed]

    out = await benchmark_service.get_teacher_benchmarks(None, "t-1")  # type: ignore[arg-type]

    assert out == []


@pytest.mark.asyncio
async def test_set_benchmark_opt_out_flips_and_clears_existing_rows() -> None:
    row = SchoolTeacherBenchmark(
        teacher_user_id="t-1",
        subject_id="subj-1",
        grade_range="9",
        region="Punjab",
        percentile=40,
        cohort_size=5,
    )
    _FakeRepo.existing = [row]

    changed = await benchmark_service.set_benchmark_opt_out(
        None,  # type: ignore[arg-type]
        teacher_user_id="t-1",
        opted_out=True,
    )

    assert changed == 1
    assert row.opted_out is True
    assert row.percentile is None
    assert row.cohort_size is None
    assert _FakeRepo.committed


@pytest.mark.asyncio
async def test_set_benchmark_opt_out_no_rows_yet_is_a_noop() -> None:
    _FakeRepo.existing = []

    changed = await benchmark_service.set_benchmark_opt_out(
        None,  # type: ignore[arg-type]
        teacher_user_id="t-1",
        opted_out=True,
    )

    assert changed == 0
    assert not _FakeRepo.committed
