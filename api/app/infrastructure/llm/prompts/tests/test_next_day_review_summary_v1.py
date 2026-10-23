"""Prompt unit tests — next_day_review_summary.v1 (T-200)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.infrastructure.llm.prompts.next_day_review_summary_v1 import (
    PROMPT_VERSION,
    ReviewClusterBrief,
    ReviewSummaryInput,
    ReviewSummaryOutput,
    render,
)


def _input(lang: str = "en") -> ReviewSummaryInput:
    return ReviewSummaryInput(
        offering_label="Grade 9 Physics",
        lecture_topic="Newton's third law",
        clusters=[
            ReviewClusterBrief(
                representative_question="Why don't action and reaction cancel?",
                question_count=6,
                unique_student_count=5,
                critical=True,
            )
        ],
        target_language=lang,  # type: ignore[arg-type]
    )


def test_prompt_version_and_render() -> None:
    call = render(_input())
    assert call.version == PROMPT_VERSION
    assert "Why don't action and reaction cancel?" in call.user
    assert "[critical]" in call.user
    assert "Grade 9 Physics" in call.user


def test_target_language_in_system_and_no_grading_rule() -> None:
    call = render(_input("ur"))
    assert "ur" in call.system
    assert "never grade" in call.system.lower()


def test_requires_at_least_one_cluster() -> None:
    with pytest.raises(ValidationError):
        ReviewSummaryInput(offering_label="x", clusters=[])


def test_output_rejects_empty_summary() -> None:
    with pytest.raises(ValidationError):
        ReviewSummaryOutput(summary="")
