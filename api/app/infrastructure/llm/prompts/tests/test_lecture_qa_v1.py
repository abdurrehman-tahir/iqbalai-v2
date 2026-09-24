"""T-158 — lecture_qa_v1 prompt unit tests (ARCH §8.6)."""

from __future__ import annotations

from app.infrastructure.llm.prompts.lecture_qa_v1 import (
    PROMPT_VERSION,
    LectureQaInput,
    QaChunkRef,
    render,
)


def test_lecture_qa_prompt_renders_sources_and_language() -> None:
    call = render(
        LectureQaInput(
            question_text="What is force?",
            highlight_text="F = ma",
            lecture_topic="Newton's Laws",
            target_language="ur",
            curriculum_chunks=[
                QaChunkRef(
                    source_id="c1",
                    source_label="Phys Curr",
                    tier="curriculum",
                    text="Force equals mass times acceleration.",
                )
            ],
        )
    )
    assert call.version == PROMPT_VERSION
    assert "ur" in call.system
    assert "What is force?" in call.user
    assert "[Curriculum" in call.user
    assert "F = ma" in call.user


def test_lecture_qa_prompt_includes_exam_overlay() -> None:
    call = render(
        LectureQaInput(
            question_text="Explain inertia",
            exam_framework_name="Matric Punjab — Physics",
            exam_strategy_summary="Show all working.",
            exam_priority_topics=["Newton's Laws (priority 0.9)"],
        )
    )
    assert "Matric Punjab" in call.user
    assert "ADDITIONAL" in call.user
    assert "Show all working" in call.user
