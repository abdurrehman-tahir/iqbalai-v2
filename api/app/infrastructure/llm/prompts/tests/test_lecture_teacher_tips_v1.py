"""Tests for lecture_teacher_tips_v1 prompt — T-124."""

from __future__ import annotations

from app.infrastructure.llm.prompts.lecture_teacher_tips_v1 import (
    PROMPT_VERSION,
    LectureTeacherTipsInput,
    render,
)


def test_render_includes_topic_subject_and_grade() -> None:
    prompt = render(
        LectureTeacherTipsInput(
            topic="Newton's Laws of Motion",
            subject_name="Physics",
            grade_level_ordinal=9,
            target_language="en",
        )
    )
    assert prompt.version == PROMPT_VERSION
    assert "Newton's Laws of Motion" in prompt.user
    assert "Physics" in prompt.user
    assert "Grade 9" in prompt.system
    assert "Respond in en" in prompt.system


def test_render_respects_target_language() -> None:
    prompt = render(
        LectureTeacherTipsInput(
            topic="Photosynthesis",
            subject_name="Biology",
            grade_level_ordinal=8,
            target_language="ur",
        )
    )
    assert "Respond in ur" in prompt.system


def test_render_instructs_general_knowledge_only() -> None:
    """Locked rule (spec §3.15): grounded in general teaching knowledge, not RAG."""
    prompt = render(
        LectureTeacherTipsInput(
            topic="Fractions",
            subject_name="Mathematics",
            grade_level_ordinal=6,
            target_language="en",
        )
    )
    assert "general teaching knowledge" in prompt.system
    assert "Do NOT reference or assume any specific" in prompt.system


def test_render_is_pure_and_deterministic() -> None:
    """render() is a pure function — same input, same output, no I/O."""
    input_data = LectureTeacherTipsInput(
        topic="Cell Division",
        subject_name="Biology",
        grade_level_ordinal=10,
        target_language="en",
    )
    assert render(input_data) == render(input_data)
