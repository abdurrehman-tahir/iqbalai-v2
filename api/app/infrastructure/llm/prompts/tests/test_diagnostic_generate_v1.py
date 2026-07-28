"""Tests for diagnostic_generate_v1 prompt — T-104."""

from __future__ import annotations

from app.infrastructure.llm.prompts.diagnostic_generate_v1 import (
    PROMPT_VERSION,
    DiagnosticGenerateInput,
    render,
)


def test_render_school_includes_grade_subject_and_count() -> None:
    prompt = render(
        DiagnosticGenerateInput(
            tenant_kind="school",
            grade_label="Grade 9",
            subject_name="Physics",
            context_json={"chapters": [{"title": "Mechanics"}]},
            question_count=18,
            target_language="en",
        )
    )
    assert prompt.version == PROMPT_VERSION
    assert "Grade 9" in prompt.user
    assert "Physics" in prompt.user
    assert "exactly 18" in prompt.user
    assert "Respond in en" in prompt.system


def test_render_independent_uses_framework_name() -> None:
    prompt = render(
        DiagnosticGenerateInput(
            tenant_kind="independent",
            framework_name="Matric Punjab Board",
            context_json={
                "topics": [{"topic_name": "Optics", "priority_weight": 0.9}],
            },
            question_count=20,
            target_language="ur",
        )
    )
    assert "Matric Punjab Board" in prompt.user
    assert "priority_weight" in prompt.user
    assert "Respond in ur" in prompt.system
