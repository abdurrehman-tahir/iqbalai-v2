"""Generate diagnostic questions via Question Bank hook or LLM — T-104."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal, cast

import structlog

from app.core.exceptions import ValidationError
from app.features.diagnostics.question_bank import try_question_bank
from app.features.diagnostics.schemas import DiagnosticQuestion
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.diagnostic_generate_v1 import (
    PROMPT_VERSION,
    DiagnosticGenerateInput,
    DiagnosticGenerateOutput,
    render,
)

logger = structlog.get_logger(__name__)

MIN_QUESTIONS = 15
MAX_QUESTIONS = 25
_MAX_ATTEMPTS = 3
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

GENERATION_FAILED_MESSAGE = (
    "Could not generate diagnostic questions after multiple attempts. Please try again later."
)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return cast(dict[str, Any], json.loads(text))


def _to_schema_questions(output: DiagnosticGenerateOutput) -> list[object]:
    return [
        DiagnosticQuestion(
            id=q.id,
            prompt=q.prompt,
            choices=list(q.choices),
            topic=q.topic,
        ).model_dump()
        for q in output.questions
    ]


def _validate_count(questions: list[object]) -> None:
    n = len(questions)
    if n < MIN_QUESTIONS or n > MAX_QUESTIONS:
        raise ValidationError(
            f"Diagnostic must have {MIN_QUESTIONS}–{MAX_QUESTIONS} questions (got {n})"
        )


async def generate_diagnostic_questions(
    *,
    tenant_kind: Literal["school", "independent"],
    target_language: Literal["en", "ur", "sd", "ps"] = "en",
    grade_label: str = "",
    subject_name: str = "",
    subject_id: str | None = None,
    framework_name: str = "",
    framework_id: str | None = None,
    context_json: dict[str, Any] | None = None,
    question_count: int = 20,
) -> list[object]:
    """Produce 15–25 diagnostic questions (bank hook first, else LLM with retries)."""
    if question_count < MIN_QUESTIONS or question_count > MAX_QUESTIONS:
        raise ValidationError(f"question_count must be between {MIN_QUESTIONS} and {MAX_QUESTIONS}")

    banked = await try_question_bank(
        tenant_kind=tenant_kind,
        subject_id=subject_id,
        framework_id=framework_id,
        grade_label=grade_label,
        limit=question_count,
    )
    if banked is not None:
        bank_payload: list[object] = [q.model_dump() for q in banked]
        _validate_count(bank_payload)
        logger.info(
            "diagnostic_questions_from_bank",
            tenant_kind=tenant_kind,
            count=len(bank_payload),
        )
        return bank_payload

    prompt_input = DiagnosticGenerateInput(
        target_language=target_language,
        tenant_kind=tenant_kind,
        grade_label=grade_label,
        subject_name=subject_name,
        framework_name=framework_name,
        context_json=context_json or {},
        question_count=question_count,
    )
    prompt = render(prompt_input)

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            raw = await chat(
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                task="diagnostic_generate",
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens,
            )
            parsed = _parse_json_payload(raw)
            output = DiagnosticGenerateOutput.model_validate(parsed)
            questions = _to_schema_questions(output)
            # Trim or reject if model overshot max
            if len(questions) > MAX_QUESTIONS:
                questions = questions[:MAX_QUESTIONS]
            _validate_count(questions)
            logger.info(
                "diagnostic_questions_generated",
                tenant_kind=tenant_kind,
                count=len(questions),
                attempt=attempt,
                prompt_version=PROMPT_VERSION,
            )
            return questions
        except Exception as exc:
            last_error = exc
            logger.warning(
                "diagnostic_question_generation_attempt_failed",
                attempt=attempt,
                error=str(exc),
                prompt_version=PROMPT_VERSION,
            )
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(0.05 * (2 ** (attempt - 1)))

    logger.error(
        "diagnostic_question_generation_failed",
        error=str(last_error) if last_error else "unknown",
        prompt_version=PROMPT_VERSION,
    )
    raise ValidationError(GENERATION_FAILED_MESSAGE)
