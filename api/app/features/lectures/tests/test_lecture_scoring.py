"""T-134 — 7-dimension quality scoring pipeline (Flow 5 §3.6 #32, ARCH §7.10).

Covers the tenant-agnostic scoring core (``_score_version``) directly — the
two locked overrides (voice_quality null for text-only edits, ai_learning=0
baseline on the first version), dimension clamping, and malformed-LLM-output
handling — plus a thin DB-wired smoke test per tenant.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from app.features.lectures.independent_tasks import (
    score_independent_lecture_version as score_independent_lecture_version_task,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVersion,
    LectureStatus,
    SchoolLecture,
    SchoolLecturePlagiarismFlag,
    SchoolLectureVersion,
)
from app.features.lectures.originality import OriginalityResult
from app.features.lectures.scoring import (
    _build_diff,
    _clamp,
    _score_version,
    score_independent_lecture_version,
    score_school_lecture_version,
)
from app.features.lectures.tasks import score_lecture_version as score_lecture_version_task
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType
from app.features.teacher_onboarding.models import TeacherProfile

_NOT_FLAGGED = OriginalityResult(
    originality_score=Decimal("0.800"),
    max_similarity=0.2,
    is_flagged=False,
    matched_version_id=None,
)
_TOPIC_RELEVANCE_MOCK = Decimal("82.50")

_VALID_LLM_JSON = (
    '{"originality": 7, "depth": 8, "cultural_relevance": 4, "engagement": 3, '
    '"alignment": 9, "voice_quality": 4, "ai_learning": 6}'
)

# --- _score_version (core, no DB) -------------------------------------------


@pytest.mark.asyncio
async def test_score_version_returns_all_seven_dimensions_plus_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def _fake_chat(messages: list[dict[str, str]], **kwargs: Any) -> str:
        calls["task"] = kwargs.get("task")
        return _VALID_LLM_JSON

    monkeypatch.setattr("app.features.lectures.scoring.chat", _fake_chat)

    scores = await _score_version(
        topic="Newton's Laws",
        original_body="AI draft body.",
        edited_body="AI draft body, heavily rewritten by the teacher.",
        edit_summary=["Applied voice edit"],
        is_first_version=False,
        active_ms=120_000,
        edits_count=5,
        char_delta=300,
        teacher_region="Punjab",
        innovation_record_context=["ground examples locally: teacher ignored this 2x"],
    )

    # Scoring is a SEPARATE LLM call routed to SCORING_MODEL (task="scoring"),
    # never the generation model — locked per ARCH §7.10 / STACK_LOCK §4.1.
    assert calls["task"] == "scoring"
    assert scores["originality"] == 7
    assert scores["depth"] == 8
    assert scores["cultural_relevance"] == 4
    assert scores["engagement"] == 3
    assert scores["alignment"] == 9
    assert scores["voice_quality"] == 4
    assert scores["ai_learning"] == 6
    assert scores["total"] == 7 + 8 + 4 + 3 + 9 + 4 + 6


@pytest.mark.asyncio
async def test_score_version_voice_quality_null_for_text_only_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locked rule: voice_quality = NULL if the edit was text-only, regardless
    of what the LLM returns for that field."""

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return _VALID_LLM_JSON  # LLM returns voice_quality=4 anyway

    monkeypatch.setattr("app.features.lectures.scoring.chat", _fake_chat)

    scores = await _score_version(
        topic="Newton's Laws",
        original_body="AI draft.",
        edited_body="Teacher-edited text, no voice used.",
        edit_summary=["Rewrote intro"],
        is_first_version=False,
        active_ms=60_000,
        edits_count=2,
        char_delta=50,
        teacher_region=None,
        innovation_record_context=[],
    )

    assert scores["voice_quality"] is None


@pytest.mark.asyncio
async def test_score_version_ai_learning_baseline_zero_on_first_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locked rule: first version has AI Learning baseline = 0, regardless of
    what the LLM returns for that field."""

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return _VALID_LLM_JSON  # LLM returns ai_learning=6 anyway

    monkeypatch.setattr("app.features.lectures.scoring.chat", _fake_chat)

    scores = await _score_version(
        topic="Newton's Laws",
        original_body="AI draft.",
        edited_body="AI draft.",
        edit_summary=None,
        is_first_version=True,
        active_ms=0,
        edits_count=0,
        char_delta=0,
        teacher_region=None,
        innovation_record_context=[],
    )

    assert scores["ai_learning"] == 0


@pytest.mark.asyncio
async def test_score_version_clamps_out_of_range_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defends the max-55 total against a non-compliant LLM response."""

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return (
            '{"originality": 99, "depth": -5, "cultural_relevance": 100, '
            '"engagement": 5, "alignment": 10, "voice_quality": 999, "ai_learning": 10}'
        )

    monkeypatch.setattr("app.features.lectures.scoring.chat", _fake_chat)

    scores = await _score_version(
        topic="T",
        original_body="A",
        edited_body="B",
        edit_summary=["Applied voice edit"],
        is_first_version=False,
        active_ms=0,
        edits_count=0,
        char_delta=0,
        teacher_region=None,
        innovation_record_context=[],
    )

    assert scores["originality"] == 10  # clamped down from 99 (cap 10)
    assert scores["depth"] == 0  # clamped up from -5 (floor 0)
    assert scores["cultural_relevance"] == 5  # clamped down from 100 (cap 5)
    assert scores["voice_quality"] == 5  # clamped down from 999 (cap 5)
    assert cast(int, scores["total"]) <= 55


@pytest.mark.asyncio
async def test_score_version_propagates_malformed_json_to_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed LLM output is the caller's problem (the tenant wrappers catch
    and log it) — ``_score_version`` itself doesn't swallow errors."""

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return "not json"

    monkeypatch.setattr("app.features.lectures.scoring.chat", _fake_chat)

    with pytest.raises(Exception):  # noqa: B017 - json.JSONDecodeError, not our concern which
        await _score_version(
            topic="T",
            original_body="A",
            edited_body="B",
            edit_summary=None,
            is_first_version=False,
            active_ms=0,
            edits_count=0,
            char_delta=0,
            teacher_region=None,
            innovation_record_context=[],
        )


# --- _build_diff / _clamp ----------------------------------------------------


def test_build_diff_reports_no_change_when_identical() -> None:
    assert "no textual change" in _build_diff("same text", "same text")


def test_build_diff_shows_a_real_diff_when_changed() -> None:
    diff = _build_diff("line one\nline two", "line one\nline three")
    assert "line two" in diff or "line three" in diff


def test_clamp_bounds_to_zero_and_cap() -> None:
    assert _clamp(-5, 10) == 0
    assert _clamp(99, 10) == 10
    assert _clamp(7, 10) == 7


# --- score_school_lecture_version / score_independent_lecture_version -------


def _fake_school_session(
    lecture: SchoolLecture,
    version: SchoolLectureVersion,
    profile: TeacherProfile | None,
    memory_rows: list[SchoolTeacherAiMemory],
) -> AsyncMock:
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == lecture.id:
            return lecture
        if model is SchoolLectureVersion and pk == version.id:
            return version
        if model is TeacherProfile and pk == lecture.teacher_user_id:
            return profile
        return None

    class _Scalars:
        def __init__(self, rows: list[Any]) -> None:
            self._rows = rows

        def all(self) -> list[Any]:
            return self._rows

    class _Result:
        def __init__(self, rows: list[Any]) -> None:
            self._rows = rows

        def scalars(self) -> _Scalars:
            return _Scalars(self._rows)

    async def _execute(*_a: Any, **_k: Any) -> _Result:
        return _Result(memory_rows)

    session.get = AsyncMock(side_effect=_get)
    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_score_school_lecture_version_writes_scores_jsonb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    profile = TeacherProfile(
        user_id="teacher-1",
        name="Ayesha",
        region_province="Punjab",
        language_preference="en",
        subject_ids=[],
    )
    memory_row = SchoolTeacherAiMemory(
        teacher_user_id="teacher-1",
        category="cultural_relevance",
        weakness_type="generic_examples",
        last_suggestion="Ground examples in local context.",
        teacher_response=TeacherResponseType.IGNORED,
    )

    session = _fake_school_session(lecture, version, profile, [memory_row])

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
        AsyncMock(return_value=_TOPIC_RELEVANCE_MOCK),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.detect_and_track_weakness_school", AsyncMock()
    )

    await score_school_lecture_version(
        session, lecture_id="lec-1", school_id="school-1", version_id="ver-2"
    )

    assert version.scores_jsonb is not None
    assert version.scores_jsonb["originality"] == 7
    assert cast(int, version.scores_jsonb["total"]) > 0
    assert version.originality_score == Decimal("0.800")
    assert version.topic_relevance_pct == _TOPIC_RELEVANCE_MOCK
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_score_school_lecture_version_raises_flag_above_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Above the locked 0.85 similarity threshold: a plagiarism flag row is
    created and Platform Admins are notified — the teacher only ever sees
    their own (low) originality score, never the flag itself (Flow 5 §3.7)."""
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
        id="ver-2", lecture_id="lec-1", version=2, body="Near-duplicate body.", edit_summary=None
    )
    session = _fake_school_session(lecture, version, None, [])

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

    flagged_result = OriginalityResult(
        originality_score=Decimal("0.070"),
        max_similarity=0.93,
        is_flagged=True,
        matched_version_id="ver-other-teacher",
    )
    notify_mock = AsyncMock()

    monkeypatch.setattr("app.features.lectures.scoring.LectureVersionRepository", _FakeVersionRepo)
    monkeypatch.setattr(
        "app.features.lectures.scoring.LectureEditSessionRepository", _FakeEditSessionRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.chat", AsyncMock(return_value=_VALID_LLM_JSON)
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.check_and_index_school_originality",
        AsyncMock(return_value=flagged_result),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.compute_topic_relevance",
        AsyncMock(return_value=_TOPIC_RELEVANCE_MOCK),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.detect_and_track_weakness_school", AsyncMock()
    )
    monkeypatch.setattr("app.features.lectures.scoring.notify_all_platform_admins", notify_mock)

    added_rows: list[Any] = []
    monkeypatch.setattr(session, "add", lambda row: added_rows.append(row))

    await score_school_lecture_version(
        session, lecture_id="lec-1", school_id="school-1", version_id="ver-2"
    )

    assert version.originality_score == Decimal("0.070")
    flags = [row for row in added_rows if isinstance(row, SchoolLecturePlagiarismFlag)]
    assert len(flags) == 1
    assert flags[0].lecture_version_id == "ver-2"
    assert flags[0].teacher_user_id == "teacher-1"
    assert flags[0].matched_lecture_version_id == "ver-other-teacher"
    assert flags[0].similarity_score == Decimal("0.930")
    notify_mock.assert_awaited_once()
    notify_kwargs = notify_mock.call_args.kwargs
    assert notify_kwargs["template_key"] == "system.plagiarism_flagged"
    # Privacy rule: no teacher/lecture identity in the notification params.
    assert "teacher" not in str(notify_kwargs["params"]).lower()
    assert "lec-1" not in str(notify_kwargs["params"])


@pytest.mark.asyncio
async def test_score_school_lecture_version_noop_for_wrong_school(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-tenant guard: a lecture from a different school must never score."""
    lecture = SchoolLecture(
        id="lec-1",
        school_id="school-OTHER",
        teacher_user_id="teacher-1",
        title="T",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-1",
    )
    version = SchoolLectureVersion(id="ver-1", lecture_id="lec-1", version=1, body="B")
    session = _fake_school_session(lecture, version, None, [])

    await score_school_lecture_version(
        session, lecture_id="lec-1", school_id="school-1", version_id="ver-1"
    )

    assert version.scores_jsonb is None
    session.commit.assert_not_awaited()


def _fake_independent_session(
    lecture: IndependentLecture, version: IndependentLectureVersion
) -> AsyncMock:
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is IndependentLecture and pk == lecture.id:
            return lecture
        if model is IndependentLectureVersion and pk == version.id:
            return version
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
async def test_score_independent_lecture_version_writes_scores_jsonb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = IndependentLecture(
        id="lec-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-1",
    )
    # First (and only) version -> ai_learning must be forced to 0.
    version = IndependentLectureVersion(id="ver-1", lecture_id="lec-1", version=1, body="Draft.")
    session = _fake_independent_session(lecture, version)

    class _FakeVersionRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_first_for_lecture(self, _lecture_id: str) -> IndependentLectureVersion:
            return version

    class _FakeEditSessionRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def list_by_version_id(self, _version_id: str) -> list[Any]:
            return []

    monkeypatch.setattr(
        "app.features.lectures.scoring.IndependentLectureVersionRepository", _FakeVersionRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.IndependentLectureEditSessionRepository",
        _FakeEditSessionRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.chat", AsyncMock(return_value=_VALID_LLM_JSON)
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.check_and_index_independent_originality",
        AsyncMock(return_value=_NOT_FLAGGED),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.compute_topic_relevance",
        AsyncMock(return_value=_TOPIC_RELEVANCE_MOCK),
    )
    monkeypatch.setattr(
        "app.features.lectures.scoring.detect_and_track_weakness_independent", AsyncMock()
    )

    await score_independent_lecture_version(session, lecture_id="lec-1", version_id="ver-1")

    assert version.scores_jsonb is not None
    assert version.scores_jsonb["ai_learning"] == 0  # first-version baseline, not the LLM's 6
    assert version.originality_score == Decimal("0.800")
    assert version.topic_relevance_pct == _TOPIC_RELEVANCE_MOCK
    session.commit.assert_awaited()


# --- Celery task wrappers (tasks.py / independent_tasks.py) -----------------
# Best-effort contract, same as generate_lecture_teacher_tips (T-124): a
# scoring failure must never raise out of the task.


def test_score_lecture_version_task_success_path() -> None:
    with patch("app.features.lectures.tasks.run_db") as mock_run_db:
        result = score_lecture_version_task.run(
            lecture_id="lec-1", school_id="school-1", version_id="ver-1"
        )

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "scored"}
    mock_run_db.assert_called_once()


def test_score_lecture_version_task_never_raises_on_failure() -> None:
    with patch("app.features.lectures.tasks.run_db", side_effect=RuntimeError("boom")):
        result = score_lecture_version_task.run(
            lecture_id="lec-1", school_id="school-1", version_id="ver-1"
        )

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "failed"}


def test_score_independent_lecture_version_task_success_path() -> None:
    with patch("app.features.lectures.independent_tasks.run_db") as mock_run_db:
        result = score_independent_lecture_version_task.run(lecture_id="lec-1", version_id="ver-1")

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "scored"}
    mock_run_db.assert_called_once()


def test_score_independent_lecture_version_task_never_raises_on_failure() -> None:
    with patch("app.features.lectures.independent_tasks.run_db", side_effect=RuntimeError("boom")):
        result = score_independent_lecture_version_task.run(lecture_id="lec-1", version_id="ver-1")

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "failed"}
