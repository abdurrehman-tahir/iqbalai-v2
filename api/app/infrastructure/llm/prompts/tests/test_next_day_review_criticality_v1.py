"""Prompt unit tests — next_day_review_criticality.v1 (T-197)."""

from __future__ import annotations

from app.infrastructure.llm.prompts.next_day_review_criticality_v1 import (
    PROMPT_VERSION,
    CriticalityInput,
    CriticalityOutput,
    render,
)


def test_prompt_version_and_render() -> None:
    call = render(CriticalityInput(question_texts=["What is force?"]))
    assert call.version == PROMPT_VERSION
    assert "What is force?" in call.user
    assert "criticality" in call.system.lower()


def test_output_bounds() -> None:
    out = CriticalityOutput(criticality=0, rationale="")
    assert out.criticality == 0
    out = CriticalityOutput(criticality=10, rationale="max")
    assert out.criticality == 10
