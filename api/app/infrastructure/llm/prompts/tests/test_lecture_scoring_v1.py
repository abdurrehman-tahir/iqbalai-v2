"""Tests for lecture_scoring_v1 prompt — T-134."""

from __future__ import annotations

from app.infrastructure.llm.prompts.lecture_scoring_v1 import (
    PROMPT_VERSION,
    LectureScoringInput,
    render,
)


def _input(**overrides: object) -> LectureScoringInput:
    defaults: dict[str, object] = dict(
        topic="Newton's Laws",
        original_body="AI-generated draft body.",
        edited_body="Teacher-edited body.",
        diff="- AI-generated draft body.\n+ Teacher-edited body.",
        edit_summary=["Applied voice edit"],
        active_ms=90_000,
        edits_count=4,
        char_delta=120,
        teacher_region="Punjab",
        innovation_record_context=["ground examples locally: ignored 2x"],
        is_first_version=False,
    )
    defaults.update(overrides)
    return LectureScoringInput(**defaults)  # type: ignore[arg-type]


def test_render_includes_original_and_edited_bodies() -> None:
    prompt = render(_input())
    assert prompt.version == PROMPT_VERSION
    assert "AI-generated draft body." in prompt.user
    assert "Teacher-edited body." in prompt.user


def test_render_includes_region_and_effort_data() -> None:
    prompt = render(_input(teacher_region="Sindh", active_ms=42_000, char_delta=17))
    assert "Sindh" in prompt.user
    assert "42000" in prompt.user
    assert "17" in prompt.user


def test_render_reports_unknown_region_when_absent() -> None:
    prompt = render(_input(teacher_region=None))
    assert "unknown" in prompt.user


def test_render_lists_all_seven_dimensions_in_system_prompt() -> None:
    prompt = render(_input())
    for dimension in (
        "originality",
        "depth",
        "cultural_relevance",
        "engagement",
        "alignment",
        "voice_quality",
        "ai_learning",
    ):
        assert dimension in prompt.system


def test_render_instructs_voice_quality_null_for_text_only() -> None:
    prompt = render(_input())
    assert "return null" in prompt.system


def test_render_instructs_ai_learning_zero_on_first_version_or_no_context() -> None:
    prompt = render(_input())
    assert "return 0" in prompt.system


def test_render_no_context_lists_render_as_none() -> None:
    prompt = render(_input(edit_summary=[], innovation_record_context=[]))
    assert "none" in prompt.user


def test_render_is_pure_and_deterministic() -> None:
    input_data = _input()
    assert render(input_data) == render(input_data)
