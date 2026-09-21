"""T-157 — question_classifier_v1 prompt unit tests (ARCH §8.6)."""

from __future__ import annotations

from app.infrastructure.llm.prompts.question_classifier_v1 import (
    PROMPT_VERSION,
    QuestionClassifierInput,
    render,
)


def test_question_classifier_prompt_renders() -> None:
    call = render(
        QuestionClassifierInput(
            question_text="What is force?",
            highlight_text="F = ma",
            lecture_excerpt="Force equals mass times acceleration.",
            target_language="ur",
        )
    )
    assert call.version == PROMPT_VERSION
    assert "ur" in call.system or "target_language" not in call.system
    assert "What is force?" in call.user
    assert "F = ma" in call.user
