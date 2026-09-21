"""T-157 — question_classifier_v1 prompt + heuristic stub tests."""

from __future__ import annotations

from app.features.student_questions.classifier import classify_question, to_model_enum
from app.features.student_questions.models import QuestionClassification
from app.infrastructure.llm.prompts.question_classifier_v1 import (
    PROMPT_VERSION,
    QuestionClassifierInput,
    QuestionClassifierOutput,
    render,
)


def test_prompt_version_and_render_shape() -> None:
    assert PROMPT_VERSION == "question_classifier.v1"
    call = render(
        QuestionClassifierInput(
            question_text="What is gravity?",
            highlight_text="gravity pulls objects",
            lecture_excerpt="Newton described gravity…",
            target_language="en",
        )
    )
    assert call.version == PROMPT_VERSION
    assert "misconception" in call.system
    assert "knowledge_gap" in call.system
    assert "What is gravity?" in call.user
    assert call.temperature <= 0.2


def test_heuristic_knowledge_gap_for_explain_phrasing() -> None:
    out = classify_question(question_text="Explain: Newton's third law")
    assert out.classification == "knowledge_gap"
    assert to_model_enum(out) == QuestionClassification.KNOWLEDGE_GAP


def test_heuristic_misconception_for_assertive_phrasing() -> None:
    out = classify_question(
        question_text="I thought heavier objects always fall faster — isn't that right?"
    )
    assert out.classification == "misconception"
    assert to_model_enum(out) == QuestionClassification.MISCONCEPTION


def test_output_model_accepts_classifier_result() -> None:
    parsed = QuestionClassifierOutput(
        classification="knowledge_gap",
        confidence=0.8,
        rationale="asks for definition",
    )
    assert parsed.classification == "knowledge_gap"
