"""Unit tests for self_study_session_v1 prompt — T-211."""

from __future__ import annotations

from app.infrastructure.llm.prompts.self_study_session_v1 import (
    PROMPT_VERSION,
    SelfStudySessionInput,
    render,
)


def test_render_injects_daily_goal() -> None:
    call = render(
        SelfStudySessionInput(
            question_text="Explain inertia",
            daily_goal="Understand Newton's Laws chapter 5",
            target_language="en",
        )
    )
    assert call.version == PROMPT_VERSION
    assert "Understand Newton's Laws chapter 5" in call.user
    assert "en" in call.system
    assert "Explain inertia" in call.user


def test_render_without_goal() -> None:
    call = render(SelfStudySessionInput(question_text="What is force?"))
    assert "(not set)" in call.user
