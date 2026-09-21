"""Question classification (T-157) — heuristic stub behind the typed-prompt interface.

Uses ``question_classifier_v1`` for prompt shape / versioning. LLM wire-up
(``llm_client.generate`` with ``response_model=QuestionClassifierOutput``) is
TODO — matching ARCH §8.6 — until the student_qa / extraction task routing
is finalized for this classifier.

Baseline accuracy target is 75%+ (Flow 6 Open Q3); Flow 9 Phase 5 refines
with Cognitive DNA training data.
"""

from __future__ import annotations

import re

from app.features.student_questions.models import QuestionClassification
from app.infrastructure.llm.prompts.question_classifier_v1 import (
    PROMPT_VERSION,
    QuestionClassifierInput,
    QuestionClassifierOutput,
    render,
)

# Cue phrases that typically signal an asserted wrong model vs a request to learn.
_MISCONCEPTION_CUES = re.compile(
    r"\b("
    r"isn'?t|aren'?t|doesn'?t|don'?t|won'?t|can'?t|"
    r"always|never|must be|should be|thought that|i think|i thought|"
    r"wrong|false|actually|but|instead"
    r")\b",
    re.IGNORECASE,
)
_KNOWLEDGE_GAP_CUES = re.compile(
    r"\b("
    r"what is|what are|what does|how does|how do|why does|why do|"
    r"explain|define|meaning of|tell me about|help me understand|"
    r"can you explain|please explain"
    r")\b",
    re.IGNORECASE,
)


def classify_question(
    *,
    question_text: str,
    highlight_text: str | None = None,
    lecture_excerpt: str = "",
    target_language: str = "en",
) -> QuestionClassifierOutput:
    """Classify a question; returns structured output compatible with the LLM path.

    TODO(T-157 LLM): call ``llm_client.generate(task=..., prompt=render(inp),
    response_model=QuestionClassifierOutput)`` and fall back to this heuristic
    only on provider failure. Task id likely ``extraction`` or a dedicated
    ``question_classify`` once added to ARCH §8.4.
    """
    lang = target_language if target_language in {"en", "ur", "sd", "ps"} else "en"
    inp = QuestionClassifierInput(
        question_text=question_text,
        highlight_text=highlight_text,
        lecture_excerpt=lecture_excerpt,
        target_language=lang,  # type: ignore[arg-type]
    )
    # Ensure the typed prompt remains the canonical contract (render is side-effect free).
    _ = render(inp)
    _ = PROMPT_VERSION

    text = question_text.strip()
    if _KNOWLEDGE_GAP_CUES.search(text) and not _MISCONCEPTION_CUES.search(text):
        return QuestionClassifierOutput(
            classification="knowledge_gap",
            confidence=0.55,
            rationale="heuristic: explanatory / definitional phrasing",
        )
    if _MISCONCEPTION_CUES.search(text):
        return QuestionClassifierOutput(
            classification="misconception",
            confidence=0.5,
            rationale="heuristic: assertive / corrective phrasing",
        )
    # Prefer knowledge_gap when unsure (matches prompt rules).
    return QuestionClassifierOutput(
        classification="knowledge_gap",
        confidence=0.35,
        rationale="heuristic: default when cues are ambiguous",
    )


def to_model_enum(result: QuestionClassifierOutput) -> QuestionClassification:
    if result.classification == "misconception":
        return QuestionClassification.MISCONCEPTION
    if result.classification == "knowledge_gap":
        return QuestionClassification.KNOWLEDGE_GAP
    return QuestionClassification.UNCLASSIFIED
