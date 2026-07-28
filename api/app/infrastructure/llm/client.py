"""LLM client — the ONLY entry point for all LLM calls in this codebase.

Per ARCH §8.1: every LLM call goes through this module. Never import openai,
groq, anthropic, or any provider SDK outside this file and its providers/ submodule.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

import structlog
from openai import AsyncOpenAI

from app.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ChatUsage:
    """A chat completion plus its token usage (for cost accounting).

    Returned by :func:`chat_with_usage` so callers that must enforce a spend
    ceiling (e.g. framework research, T-093) can meter tokens without importing
    a provider SDK — the LLM chokepoint stays in this module (ARCH §8.1/§8.13).
    """

    text: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _get_client(task: str = "") -> AsyncOpenAI:
    """Build an OpenAI-compatible client for the configured provider.

    Task-specific model overrides per ARCH §8.4:
    - lecture_generation → LECTURE_GEN_MODEL
    - chatbot → CHATBOT_MODEL
    - student_qa → STUDENT_QA_MODEL
    - va → VA_MODEL
    - scoring → SCORING_MODEL
    """
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )


def _resolve_model(task: str = "") -> str:
    """Return the model name for the given task, falling back to LLM_MODEL."""
    settings = get_settings()
    task_overrides: dict[str, str] = {
        "lecture_generation": settings.LECTURE_GEN_MODEL,
        "chatbot": settings.CHATBOT_MODEL,
        "student_qa": settings.STUDENT_QA_MODEL,
        "va": settings.VA_MODEL,
        "scoring": settings.SCORING_MODEL,
        # T-104: diagnostic questions share scoring-tier routing until a dedicated env exists.
        "diagnostic_generate": settings.SCORING_MODEL,
    }
    override = task_overrides.get(task, "")
    return override if override else settings.LLM_MODEL


async def chat(
    messages: list[dict[str, str]],
    task: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    attached_images: list[str] | None = None,
) -> str:
    """Send a chat completion request and return the response text.

    Args:
        messages: OpenAI-format message list [{"role": "...", "content": "..."}]
        task: task identifier for model routing (see _resolve_model)
        temperature: sampling temperature
        max_tokens: maximum tokens to generate
        attached_images: base64-encoded images — if present, routes to vision model (ARCH §8.22)

    Returns:
        The assistant's response text.
    """
    settings = get_settings()
    model = _resolve_model(task)

    # Vision routing stub (ARCH §8.22)
    if attached_images:
        logger.debug("llm_vision_routing", task=task, image_count=len(attached_images))

    client = _get_client(task)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.info(
            "llm_chat_complete",
            task=task,
            provider=settings.LLM_PROVIDER,
            model=model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        return content
    except Exception as exc:
        logger.error("llm_chat_failed", task=task, provider=settings.LLM_PROVIDER, error=str(exc))
        raise


async def chat_with_usage(
    messages: list[dict[str, str]],
    task: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatUsage:
    """Like :func:`chat`, but also returns token usage for cost metering.

    Callers enforcing a USD ceiling (framework research) need per-call token
    counts. Usage may be absent from a provider response; missing counts are
    reported as 0 (a conservative under-count is preferable to failing the run).
    """
    settings = get_settings()
    model = _resolve_model(task)
    client = _get_client(task)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        logger.info(
            "llm_chat_complete",
            task=task,
            provider=settings.LLM_PROVIDER,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return ChatUsage(
            text=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception as exc:
        logger.error("llm_chat_failed", task=task, provider=settings.LLM_PROVIDER, error=str(exc))
        raise


async def stream_chat(
    messages: list[dict[str, str]],
    task: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion, yielding text chunks as they arrive."""
    settings = get_settings()
    model = _resolve_model(task)
    client = _get_client(task)

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as exc:
        logger.error("llm_stream_failed", task=task, provider=settings.LLM_PROVIDER, error=str(exc))
        raise
