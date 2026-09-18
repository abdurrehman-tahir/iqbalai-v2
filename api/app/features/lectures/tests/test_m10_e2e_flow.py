"""T-140 — M-10 end-to-end flow smoke (Flow 5 §3.5-§3.12).

Playwright can't launch in this dev environment (Alpine/musl — the same
pre-existing gap noted since T-130), so the browser-level happy path lives
in ``frontend/e2e/lecture-scoring-benchmark-e2e.spec.ts`` (authored, not
runnable here; see that file's header). This test is the backend-side
substitute: it chains the actual T-134/T-139 functions (not just each in
isolation, as their own dedicated test files already cover) to prove the
pieces connect —

    edit -> new version -> scoring (mocked LLM) -> originality/relevance
    -> weekly benchmark recompute -> admin comparative metrics

— and asserts the three acceptance properties Playwright would otherwise
check: version immutability, anonymity on the teacher-facing benchmark
surface, and that the admin-facing surface (correctly) is NOT anonymized.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from app.core.tests.test_idempotency import FakeRedis
from app.features.admin_metrics import service as admin_metrics_service
from app.features.admin_metrics.repository import TeacherMetricsRow
from app.features.admin_metrics.service import MetricsFilters
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureVersion
from app.features.lectures.originality import OriginalityResult
from app.features.lectures.scoring import score_school_lecture_version
from app.features.teacher_coaching import benchmark_service
from app.features.teacher_coaching.benchmark_repository import ScoredVersionRow
from app.features.teacher_coaching.models import SchoolTeacherBenchmark
from app.features.teacher_onboarding.models import TeacherProfile

_NOT_FLAGGED = OriginalityResult(
    originality_score=Decimal("0.800"),
    max_similarity=0.2,
    is_flagged=False,
    matched_version_id=None,
)
_VALID_LLM_JSON = (
    '{"originality": 8, "depth": 7, "cultural_relevance": 4, "engagement": 4, '
    '"alignment": 9, "voice_quality": 4, "ai_learning": 6}'
)


class _FakeBenchmarkRepo:
    scored_versions: list[ScoredVersionRow] = []
    existing: list[SchoolTeacherBenchmark] = []
    added: list[SchoolTeacherBenchmark] = []

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
            if row.teacher_user_id == teacher_user_id and row.percentile is not None
        ]

    async def list_all_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherBenchmark]:
        return [r for r in self.existing if r.teacher_user_id == teacher_user_id]

    def add(self, row: SchoolTeacherBenchmark) -> None:
        self.added.append(row)
        self.existing.append(row)

    async def commit(self) -> None:
        pass

    async def get_subject_names(self, subject_ids: list[str]) -> dict[str, str]:
        return {sid: "Mathematics" for sid in subject_ids}


class _FakeAdminMetricsRepo:
    rows: list[TeacherMetricsRow] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_scored_versions(
        self, *, school_ids: list[str] | None
    ) -> list[TeacherMetricsRow]:
        if school_ids is None:
            return list(self.rows)
        return [r for r in self.rows if r.school_id in school_ids]

    async def list_school_ids_for_district(self, district_id: str) -> list[str]:
        return []


def _fake_school_session(lecture: SchoolLecture, version: SchoolLectureVersion) -> AsyncMock:
    session = AsyncMock()
    profile = TeacherProfile(
        user_id=lecture.teacher_user_id,
        name="Ayesha",
        region_province="Punjab",
        language_preference="en",
        subject_ids=[],
    )

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == lecture.id:
            return lecture
        if model is SchoolLectureVersion and pk == version.id:
            return version
        if model is TeacherProfile and pk == lecture.teacher_user_id:
            return profile
        return None

    class _Scalars:
        def all(self) -> list[Any]:
            return []

    class _Result:
        def scalars(self) -> _Scalars:
            return _Scalars()

    async def _execute(*_a: Any, **_k: Any) -> _Result:
        return _Result()

    session.get = AsyncMock(side_effect=_get)
    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_edit_to_admin_metrics_flow_preserves_immutability_and_privacy_tiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --- Stage 1: teacher edits and saves -> new version -> scoring (T-134/135/136) ---
    lecture = SchoolLecture(
        id="lec-1",
        school_id="school-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-2",
    )
    first_version = SchoolLectureVersion(
        id="ver-1", lecture_id="lec-1", version=1, body="AI draft."
    )
    version = SchoolLectureVersion(
        id="ver-2", lecture_id="lec-1", version=2, body="Teacher-edited body.", edit_summary=None
    )
    session = _fake_school_session(lecture, version)

    class _FakeVersionRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_first_for_lecture(self, _lecture_id: str) -> SchoolLectureVersion:
            return first_version

    class _FakeEditSessionRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def list_by_version_id(self, _version_id: str) -> list[Any]:
            return []

    monkeypatch.setattr("app.features.lectures.scoring.LectureVersionRepository", _FakeVersionRepo)
    monkeypatch.setattr(
        "app.features.lectures.scoring.LectureEditSessionRepository", _FakeEditSessionRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.chat", AsyncMock(return_value=_VALID_LLM_JSON)
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.check_and_index_school_originality",
        AsyncMock(return_value=_NOT_FLAGGED),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.compute_topic_relevance",
        AsyncMock(return_value=Decimal("88.0")),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.detect_and_track_weakness_school", AsyncMock()
    )
    monkeypatch.setattr("app.features.lectures.scoring.notify_scoring_complete", AsyncMock())

    version_id_before, version_number_before = version.id, version.version

    await score_school_lecture_version(
        session, lecture_id="lec-1", school_id="school-1", version_id="ver-2"
    )

    # Immutability: scoring writes onto the SAME version row — no new row, no
    # version-number bump. Only the scoring-derived columns changed.
    assert version.id == version_id_before
    assert version.version == version_number_before
    assert version.scores_jsonb is not None
    assert cast(int, version.scores_jsonb["total"]) > 0
    assert version.topic_relevance_pct == Decimal("88.0")

    # --- Stage 2: weekly benchmark recompute (T-139 #37) ------------------------
    monkeypatch.setattr(
        "app.features.teacher_coaching.benchmark_service.SchoolTeacherBenchmarkRepository",
        _FakeBenchmarkRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.benchmark_service._notify_benchmark_updates", AsyncMock()
    )
    _FakeBenchmarkRepo.scored_versions = [
        ScoredVersionRow(
            teacher_user_id="teacher-1",
            subject_id="subj-1",
            grade_level_ordinal="9",
            region="Punjab",
            scores_jsonb=version.scores_jsonb,
        ),
        ScoredVersionRow(
            teacher_user_id="teacher-2",
            subject_id="subj-1",
            grade_level_ordinal="9",
            region="Punjab",
            scores_jsonb={"total": 20},
        ),
        ScoredVersionRow(
            teacher_user_id="teacher-3",
            subject_id="subj-1",
            grade_level_ordinal="9",
            region="Punjab",
            scores_jsonb={"total": 45},
        ),
    ]
    _FakeBenchmarkRepo.existing = []
    _FakeBenchmarkRepo.added = []

    beat_result = await benchmark_service.compute_and_store_weekly_benchmarks(session)
    assert beat_result["cohorts_computed"] == 1

    teacher_1_benchmark = next(
        row for row in _FakeBenchmarkRepo.added if row.teacher_user_id == "teacher-1"
    )
    assert teacher_1_benchmark.percentile is not None

    # --- Stage 3: teacher-facing benchmark view is anonymized (Flow 5 §3.11) ---
    _FakeBenchmarkRepo.existing = list(_FakeBenchmarkRepo.added)
    teacher_view = await benchmark_service.get_teacher_benchmarks(session, "teacher-1")
    assert len(teacher_view) == 1
    assert set(teacher_view[0].keys()) == {
        "id",
        "subject_name",
        "grade_range",
        "region",
        "top_percent",
    }
    # Structurally cannot leak a name or a matched-teacher identity — no such
    # field exists on the response shape at all.
    assert "teacher_name" not in teacher_view[0]
    assert "matched" not in str(teacher_view[0]).lower()

    # --- Stage 4: admin comparative metrics is NOT anonymized (Flow 5 §3.12 #38) ---
    monkeypatch.setattr(
        "app.features.admin_metrics.service.AdminTeacherMetricsRepository", _FakeAdminMetricsRepo
    )
    monkeypatch.setattr("app.features.admin_metrics.service.get_redis", lambda: FakeRedis())

    _FakeAdminMetricsRepo.rows = [
        TeacherMetricsRow(
            teacher_user_id="teacher-1",
            teacher_name="Ayesha Khan",
            school_id="school-1",
            school_name="Model School",
            subject_id="subj-1",
            subject_name="Mathematics",
            grade_level_ordinal="9",
            lecture_id="lec-1",
            scores_jsonb=version.scores_jsonb,
            topic_relevance_pct=88.0,
        ),
        TeacherMetricsRow(
            teacher_user_id="teacher-other",
            teacher_name="Bilal Ahmed",
            school_id="school-2",
            school_name="Other School",
            subject_id="subj-1",
            subject_name="Mathematics",
            grade_level_ordinal="9",
            lecture_id="lec-9",
            scores_jsonb={"total": 30},
            topic_relevance_pct=70.0,
        ),
    ]

    school_admin_view = await admin_metrics_service.get_teacher_metrics(
        session,
        claims={"school_id": "school-1"},
        caller_role="school_admin",
        filters=MetricsFilters(),
    )
    # Admin sees real names (unlike the teacher-facing surface above) — and
    # only their own school (§6.19 scope restriction).
    assert len(school_admin_view) == 1
    assert school_admin_view[0].teacher_name == "Ayesha Khan"
    assert school_admin_view[0].school_name == "Model School"

    platform_admin_view = await admin_metrics_service.get_teacher_metrics(
        session,
        claims={},
        caller_role="platform_admin",
        filters=MetricsFilters(),
    )
    assert {row.teacher_name for row in platform_admin_view} == {"Ayesha Khan", "Bilal Ahmed"}
