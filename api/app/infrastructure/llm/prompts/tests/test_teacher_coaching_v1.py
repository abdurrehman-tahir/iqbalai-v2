"""Tests for teacher_coaching_v1 prompt — T-138."""

from __future__ import annotations

from app.infrastructure.llm.prompts.teacher_coaching_v1 import (
    PROMPT_VERSION,
    TeacherCoachingInput,
    render,
)


def test_render_includes_weakness_and_frequency() -> None:
    prompt = render(
        TeacherCoachingInput(
            weakness_type="originality",
            frequency=2,
            last_suggestion=None,
            teacher_response="none",
            region="Punjab",
        )
    )
    assert prompt.version == PROMPT_VERSION
    assert "originality" in prompt.user
    assert "2" in prompt.user
    assert "Punjab" in prompt.user


def test_render_reports_unknown_region_when_absent() -> None:
    prompt = render(
        TeacherCoachingInput(
            weakness_type="depth", frequency=1, last_suggestion=None, teacher_response="none"
        )
    )
    assert "unknown" in prompt.user


def test_render_flags_ignored_prior_suggestion_for_adaptation() -> None:
    prompt = render(
        TeacherCoachingInput(
            weakness_type="cultural_relevance",
            frequency=3,
            last_suggestion="Try grounding in local Punjab examples.",
            teacher_response="ignored",
        )
    )
    assert "Try grounding in local Punjab examples." in prompt.user
    assert "ignored" in prompt.user


def test_render_system_prompt_locks_coaching_not_grading_tone() -> None:
    """Flow 5 §3.10 locked rule."""
    prompt = render(
        TeacherCoachingInput(
            weakness_type="engagement", frequency=1, last_suggestion=None, teacher_response="none"
        )
    )
    assert "NOT grading" in prompt.system
    assert "never mention scores" in prompt.system


def test_render_instructs_a_different_angle_when_ignored() -> None:
    prompt = render(
        TeacherCoachingInput(
            weakness_type="alignment", frequency=2, last_suggestion="x", teacher_response="ignored"
        )
    )
    assert "genuinely different approach" in prompt.system


def test_render_is_pure_and_deterministic() -> None:
    input_data = TeacherCoachingInput(
        weakness_type="originality",
        frequency=1,
        last_suggestion=None,
        teacher_response="none",
        region="Sindh",
    )
    assert render(input_data) == render(input_data)
