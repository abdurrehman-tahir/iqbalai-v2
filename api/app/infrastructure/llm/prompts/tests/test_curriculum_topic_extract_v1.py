"""Tests for curriculum_topic_extract_v1 prompt — T-057."""

from __future__ import annotations

from app.infrastructure.llm.prompts.curriculum_topic_extract_v1 import (
    PROMPT_VERSION,
    CurriculumTopicExtractInput,
    render,
)


def test_render_includes_title_and_truncates_long_document() -> None:
    long_text = "Chapter 1\n" + ("Motion and force. " * 2000)
    prompt = render(
        CurriculumTopicExtractInput(
            title="Punjab Physics Grade 9",
            language="en",
            document_text=long_text,
        )
    )

    assert prompt.version == PROMPT_VERSION
    assert "Punjab Physics Grade 9" in prompt.user
    assert "document truncated" in prompt.user
    assert prompt.temperature == 0.2


def test_render_system_uses_target_language() -> None:
    prompt = render(
        CurriculumTopicExtractInput(
            title="Urdu Curriculum",
            language="ur",
            document_text="باب 1: حرکت",
        )
    )

    assert "Respond in ur" in prompt.system
