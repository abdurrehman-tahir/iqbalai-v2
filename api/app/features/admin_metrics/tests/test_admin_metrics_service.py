"""T-139 — admin comparative teacher metrics service (Flow 5 §3.11 #38)."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import PermissionDeniedError
from app.core.tests.test_idempotency import FakeRedis
from app.features.admin_metrics import service
from app.features.admin_metrics.repository import TeacherMetricsRow
from app.features.admin_metrics.service import MetricsFilters


class _FakeRepo:
    scored_versions: list[TeacherMetricsRow] = []
    school_ids_by_district: dict[str, list[str]] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_scored_versions(
        self, *, school_ids: list[str] | None
    ) -> list[TeacherMetricsRow]:
        if school_ids is None:
            return list(self.scored_versions)
        return [r for r in self.scored_versions if r.school_id in school_ids]

    async def list_school_ids_for_district(self, district_id: str) -> list[str]:
        return list(self.school_ids_by_district.get(district_id, []))


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.scored_versions = []
    _FakeRepo.school_ids_by_district = {}
    monkeypatch.setattr(
        "app.features.admin_metrics.service.AdminTeacherMetricsRepository", _FakeRepo
    )
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.features.admin_metrics.service.get_redis", lambda: fake_redis)


def _row(
    teacher: str,
    total: float,
    *,
    school_id: str = "school-1",
    subject_id: str = "subj-1",
    grade: str = "9",
    lecture_id: str = "lec-1",
    topic_relevance_pct: float | None = 80.0,
) -> TeacherMetricsRow:
    return TeacherMetricsRow(
        teacher_user_id=teacher,
        teacher_name=f"Teacher {teacher}",
        school_id=school_id,
        school_name=f"School {school_id}",
        subject_id=subject_id,
        subject_name="Mathematics",
        grade_level_ordinal=grade,
        lecture_id=lecture_id,
        scores_jsonb={
            "originality": 8,
            "depth": 7,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
            "voice_quality": None,
            "ai_learning": 6,
            "total": total,
        },
        topic_relevance_pct=topic_relevance_pct,
    )


@pytest.mark.asyncio
async def test_school_admin_scoped_to_own_school() -> None:
    _FakeRepo.scored_versions = [
        _row("t-1", 40.0, school_id="school-1"),
        _row("t-2", 90.0, school_id="school-2"),
    ]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={"school_id": "school-1"},
        caller_role="school_admin",
        filters=MetricsFilters(),
    )

    assert len(rows) == 1
    assert rows[0].teacher_user_id == "t-1"
    assert rows[0].school_id == "school-1"


@pytest.mark.asyncio
async def test_school_admin_without_school_id_claim_is_denied() -> None:
    with pytest.raises(PermissionDeniedError):
        await service.get_teacher_metrics(
            None,  # type: ignore[arg-type]
            claims={},
            caller_role="school_admin",
            filters=MetricsFilters(),
        )


@pytest.mark.asyncio
async def test_district_admin_scoped_to_district_schools() -> None:
    _FakeRepo.school_ids_by_district = {"district-1": ["school-1", "school-2"]}
    _FakeRepo.scored_versions = [
        _row("t-1", 40.0, school_id="school-1"),
        _row("t-2", 90.0, school_id="school-2"),
        _row("t-3", 20.0, school_id="school-3"),  # different district
    ]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={"district_id": "district-1"},
        caller_role="district_admin",
        filters=MetricsFilters(),
    )

    teacher_ids = {r.teacher_user_id for r in rows}
    assert teacher_ids == {"t-1", "t-2"}


@pytest.mark.asyncio
async def test_platform_admin_sees_every_school() -> None:
    _FakeRepo.scored_versions = [
        _row("t-1", 40.0, school_id="school-1"),
        _row("t-2", 90.0, school_id="school-2"),
    ]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )

    assert {r.teacher_user_id for r in rows} == {"t-1", "t-2"}


@pytest.mark.asyncio
async def test_school_filter_outside_scope_is_denied() -> None:
    with pytest.raises(PermissionDeniedError):
        await service.get_teacher_metrics(
            None,  # type: ignore[arg-type]
            claims={"school_id": "school-1"},
            caller_role="school_admin",
            filters=MetricsFilters(school_id="school-2"),
        )


@pytest.mark.asyncio
async def test_subject_and_grade_filters_narrow_results() -> None:
    _FakeRepo.scored_versions = [
        _row("t-1", 40.0, subject_id="subj-1", grade="9"),
        _row("t-2", 90.0, subject_id="subj-2", grade="10"),
    ]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(subject_id="subj-1", grade_range="9"),
    )

    assert len(rows) == 1
    assert rows[0].teacher_user_id == "t-1"


@pytest.mark.asyncio
async def test_multiple_versions_average_per_teacher_subject_grade() -> None:
    _FakeRepo.scored_versions = [
        _row("t-1", 40.0, lecture_id="lec-1"),
        _row("t-1", 60.0, lecture_id="lec-2"),
    ]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )

    assert len(rows) == 1
    assert rows[0].avg_total == 50.0
    assert rows[0].lecture_count == 2


@pytest.mark.asyncio
async def test_voice_quality_none_does_not_poison_average() -> None:
    _FakeRepo.scored_versions = [_row("t-1", 40.0)]

    rows = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )

    assert rows[0].avg_voice_quality is None


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache_without_hitting_repo() -> None:
    _FakeRepo.scored_versions = [_row("t-1", 40.0)]

    first = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )
    _FakeRepo.scored_versions = []  # repo now empty; cache should still serve the old result

    second = await service.get_teacher_metrics(
        None,  # type: ignore[arg-type]
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )

    assert first == second
    assert len(second) == 1
