"""T-144 calibration + T-143 quiz generation unit tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.cognitive_dna.models import SchoolCognitiveDna
from app.features.quizzes.calibration import (
    CognitiveDnaCalibrationProvider,
    DiagnosticSeedCalibrationProvider,
)
from app.features.quizzes.models import QuizQuestionDifficulty
from app.features.quizzes.schemas import CalibrationSource
from app.infrastructure.llm.prompts import quiz_generate_v1


@pytest.mark.anyio
async def test_no_seed_falls_back_to_grade_default(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = DiagnosticSeedCalibrationProvider(MagicMock())

    async def _none(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(provider._dna, "get_for_scope", _none)
    result = await provider.resolve(
        student_user_id="stu-1", subject_id="subj-1", lecture_topic="Newton"
    )
    assert result.target_difficulty == QuizQuestionDifficulty.GRADE_DEFAULT
    assert result.profile.source == CalibrationSource.GRADE_DEFAULT


@pytest.mark.anyio
async def test_high_confidence_yields_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = DiagnosticSeedCalibrationProvider(MagicMock())
    row = SchoolCognitiveDna(
        student_user_id="stu-1",
        subject_id="subj-1",
        topic_confidence_jsonb={"Newton's Laws": 0.92},
        focus_areas_jsonb=[],
        last_updated_at=datetime.now(timezone.utc),
    )

    async def _row(**_kwargs: object) -> SchoolCognitiveDna:
        return row

    monkeypatch.setattr(provider._dna, "get_for_scope", _row)
    result = await provider.resolve(
        student_user_id="stu-1", subject_id="subj-1", lecture_topic="Newton's Laws"
    )
    assert result.target_difficulty == QuizQuestionDifficulty.APPLIED
    assert result.profile.source == CalibrationSource.DIAGNOSTIC_SEED


@pytest.mark.anyio
async def test_focus_area_yields_foundational(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = DiagnosticSeedCalibrationProvider(MagicMock())
    row = SchoolCognitiveDna(
        student_user_id="stu-1",
        subject_id="subj-1",
        topic_confidence_jsonb={"Optics": 0.3},
        focus_areas_jsonb=[{"topic": "Optics", "reason": "weak"}],
        last_updated_at=datetime.now(timezone.utc),
    )

    async def _row(**_kwargs: object) -> SchoolCognitiveDna:
        return row

    monkeypatch.setattr(provider._dna, "get_for_scope", _row)
    result = await provider.resolve(
        student_user_id="stu-1", subject_id="subj-1", lecture_topic="Optics"
    )
    assert result.target_difficulty == QuizQuestionDifficulty.FOUNDATIONAL


@pytest.mark.anyio
async def test_m18_hook_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="M-18"):
        await CognitiveDnaCalibrationProvider().resolve(
            student_user_id="stu-1", subject_id=None, lecture_topic="x"
        )


def test_quiz_prompt_requests_5_to_10_with_source() -> None:
    messages = quiz_generate_v1.render(
        quiz_generate_v1.QuizGenerateInput(
            topic="Newton",
            lecture_excerpt="F=ma means force equals mass times acceleration.",
            target_difficulty="applied",
            question_count=7,
        )
    )
    joined = " ".join(m["content"] for m in messages)
    assert "source_excerpt" in joined
    assert "7" in joined


@pytest.mark.anyio
async def test_enqueue_one_task_per_student(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.lectures.models import LectureStatus, SchoolLecture
    from app.features.quizzes import generation as gen_mod

    lecture = SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="off-1",
        teacher_user_id="t-1",
        title="T",
        topic="Newton",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-1",
    )

    offering = MagicMock(grade_id="g-1", academic_session="2025-26", subject_id="s-1")
    enrollments = [
        MagicMock(student_user_id="stu-1", section_id="sec-1"),
        MagicMock(student_user_id="stu-2", section_id="sec-1"),
    ]
    enqueued: list[dict[str, Any]] = []

    class _Task:
        @staticmethod
        def apply_async(*, kwargs: dict[str, Any]) -> None:
            enqueued.append(kwargs)

    monkeypatch.setattr(
        "app.features.quizzes.generation.OfferingRepository.get_by_id",
        AsyncMock(return_value=offering),
    )
    monkeypatch.setattr(
        "app.features.quizzes.generation.StudentEnrollmentRepository.list_active_for_grade",
        AsyncMock(return_value=enrollments),
    )
    monkeypatch.setattr(
        "app.features.lectures.repository.LectureAssignmentRepository.list_by_lecture",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.features.quizzes.generation.UserRepository.get_by_id",
        AsyncMock(side_effect=lambda uid: MagicMock(id=uid)),
    )
    monkeypatch.setattr(gen_mod, "generate_quiz_for_student", _Task, raising=False)
    # Import path used inside enqueue:
    monkeypatch.setattr(
        "app.features.quizzes.tasks.generate_quiz_for_student",
        _Task,
    )

    count = await gen_mod.enqueue_quiz_generation_for_lecture(MagicMock(), lecture=lecture)
    assert count == 2
    assert len(enqueued) == 2
    assert {e["student_user_id"] for e in enqueued} == {"stu-1", "stu-2"}
