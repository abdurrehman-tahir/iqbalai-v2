"""Diagnostic question generation tests — T-104."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ValidationError
from app.features.diagnostics.question_generation import (
    GENERATION_FAILED_MESSAGE,
    generate_diagnostic_questions,
)


def _llm_payload(count: int = 20) -> str:
    questions = [
        {
            "id": f"q{i}",
            "prompt": f"Question {i} about Newton?",
            "choices": ["A", "B", "C", "D"],
            "topic": "Mechanics",
        }
        for i in range(1, count + 1)
    ]
    return json.dumps({"questions": questions})


@pytest.mark.asyncio
async def test_school_generation_uses_llm_when_bank_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.try_question_bank",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.chat",
        AsyncMock(return_value=_llm_payload(20)),
    )
    questions = await generate_diagnostic_questions(
        tenant_kind="school",
        grade_label="Grade 9",
        subject_name="Physics",
        subject_id="subj-1",
        context_json={"chapters": [{"title": "Mechanics"}]},
        question_count=20,
    )
    assert 15 <= len(questions) <= 25
    first = questions[0]
    assert isinstance(first, dict)
    assert first["id"] == "q1"


@pytest.mark.asyncio
async def test_independent_generation_calibrated_by_framework_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_mock = AsyncMock(return_value=_llm_payload(18))
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.try_question_bank",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.chat",
        chat_mock,
    )
    questions = await generate_diagnostic_questions(
        tenant_kind="independent",
        framework_name="Matric Punjab",
        framework_id="fw-1",
        context_json={
            "topics": [
                {"topic_name": "Optics", "priority_weight": 0.95},
                {"topic_name": "Waves", "priority_weight": 0.4},
            ]
        },
        question_count=18,
    )
    assert len(questions) == 18
    assert chat_mock.await_args is not None
    call_kwargs = chat_mock.await_args.kwargs
    assert call_kwargs["task"] == "diagnostic_generate"
    assert "Optics" in call_kwargs["messages"][1]["content"]


@pytest.mark.asyncio
async def test_question_bank_hook_always_falls_back_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.diagnostics.question_bank import try_question_bank

    assert await try_question_bank(tenant_kind="school", subject_id="s1") is None


@pytest.mark.asyncio
async def test_generation_retries_then_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.try_question_bank",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.chat",
        AsyncMock(side_effect=RuntimeError("upstream down")),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.asyncio.sleep",
        AsyncMock(),
    )
    with pytest.raises(ValidationError, match="Could not generate"):
        await generate_diagnostic_questions(
            tenant_kind="school",
            grade_label="9",
            subject_name="Math",
            question_count=20,
        )


@pytest.mark.asyncio
async def test_rejects_out_of_range_count_from_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.try_question_bank",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.chat",
        AsyncMock(return_value=_llm_payload(5)),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.question_generation.asyncio.sleep",
        AsyncMock(),
    )
    with pytest.raises(ValidationError) as exc:
        await generate_diagnostic_questions(
            tenant_kind="school",
            subject_name="Physics",
            question_count=20,
        )
    assert GENERATION_FAILED_MESSAGE in str(exc.value) or "15" in str(exc.value)
