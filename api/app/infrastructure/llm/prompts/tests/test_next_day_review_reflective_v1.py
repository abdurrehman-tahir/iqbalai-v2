"""Prompt unit tests — next_day_review_reflective.v1 (T-202)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.infrastructure.llm.prompts.next_day_review_reflective_v1 import (
    PROMPT_VERSION,
    ReflectiveInput,
    ReflectiveOutput,
    contains_grading_language,
    render,
)


def test_prompt_version_and_render() -> None:
    call = render(
        ReflectiveInput(
            offering_label="Grade 9 Physics",
            lecture_topic="Newton's third law",
            misconceptions=["Why don't action and reaction cancel?"],
            target_language="sd",
        )
    )
    assert call.version == PROMPT_VERSION
    assert "Why don't action and reaction cancel?" in call.user
    assert "never grading" in call.system
    assert "sd" in call.system


@pytest.mark.parametrize(
    "text",
    [
        "Your explanation scored poorly — how will you fix it?",
        "What mistake did you make in the demo?",
        "You should have used a diagram; will you?",
    ],
)
def test_grading_language_is_detected(text: str) -> None:
    assert contains_grading_language(text) is True


def test_coaching_question_passes() -> None:
    q = "Would a worked example with everyday objects make the action-reaction pair concrete?"
    assert contains_grading_language(q) is False


def test_requires_a_misconception() -> None:
    with pytest.raises(ValidationError):
        ReflectiveInput(offering_label="x", misconceptions=[])


def test_output_rejects_empty_question() -> None:
    with pytest.raises(ValidationError):
        ReflectiveOutput(question="")
