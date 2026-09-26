"""LLM client — the ONLY entry point for all LLM calls in this codebase.

Per ARCH §8.1: every LLM call goes through this module. Never import openai,
groq, anthropic, or any provider SDK outside this file and its providers/ submodule.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import structlog
from openai import AsyncOpenAI

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Vision routing (T-168 / ARCH §8.22): the ~2-3x per-call cost multiplier a
# vision-capable model carries vs. the default text model, for observability
# only (not billing-grade) — Flow 6 §3.5 accepts this cost when images attach.
VISION_COST_MULTIPLIER = 2.5


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


def _strip_provider_prefix(model: str) -> str:
    """Strip a leading ``groq:`` provider prefix, if present (T-168).

    ``LLM_VISION_MODEL`` may be configured either as a bare model id or with
    an explicit ``groq:`` prefix (some ops tooling names Groq-hosted models
    this way) — the OpenAI-compatible client call always wants the bare id.
    """
    if model.startswith("groq:"):
        return model.split(":", 1)[1]
    return model


def _resolve_vision_model() -> str:
    """Return the configured vision-capable model (ARCH §8.22)."""
    settings = get_settings()
    return _strip_provider_prefix(settings.LLM_VISION_MODEL)


def _looks_like_storage_key(value: str) -> bool:
    """Heuristic: is ``value`` a MinIO object key rather than a base64 blob?

    Object keys built by ``files.pipeline._build_minio_key`` always look like
    ``{prefix}/{scope}/{YYYY}/{MM}/{DD}/{upload_id}/{filename}`` — at least
    four ``/`` separators and no ``=`` padding. Base64-encoded image payloads
    are long unbroken character runs that are vanishingly unlikely to hit that
    many ``/`` characters without also having ``=`` padding, and are typically
    far longer than a storage key. This keeps the vision-routing helper free
    of any dependency on the ``files`` feature (layer purity, ARCH §2.4).
    """
    if not value or value.startswith("data:"):
        return False
    if "=" in value:
        return False
    return value.count("/") >= 3 and len(value) < 600


def _sniff_image_mime(data: bytes) -> str:
    """Best-effort magic-byte sniff for the three student-image formats."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _to_data_url(image: str) -> str:
    """Resolve one ``attached_images`` entry to a ``data:`` URL for the model.

    MinIO-key entries are downloaded via ``storage.client.download_bytes``;
    anything else is treated as an already-base64-encoded image payload (or a
    pre-built ``data:`` URL, passed through unchanged).
    """
    if image.startswith("data:"):
        return image
    if _looks_like_storage_key(image):
        from app.infrastructure.storage.client import download_bytes

        try:
            data = download_bytes("images", image)
        except Exception as exc:
            logger.warning("llm_vision_image_download_failed", key=image, error=str(exc))
            return ""
        mime = _sniff_image_mime(data)
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    # Already base64 — default to JPEG; the provider sniffs actual content.
    return f"data:image/jpeg;base64,{image}"


def inject_images_into_messages(
    messages: list[dict[str, Any]],
    attached_images: list[str],
) -> list[dict[str, Any]]:
    """Fold ``attached_images`` into the last user message as multimodal parts.

    Per ARCH §8.22: the vision model receives the original text content plus
    one ``image_url`` part per attached image (OpenAI-compatible multimodal
    content-part shape, which Groq's vision endpoint also accepts). Returns a
    new list — callers' original ``messages`` are never mutated.
    """
    if not attached_images:
        return messages

    image_parts: list[dict[str, Any]] = []
    for image in attached_images:
        data_url = _to_data_url(image)
        if not data_url:
            continue
        image_parts.append({"type": "image_url", "image_url": {"url": data_url}})

    if not image_parts:
        return messages

    result = [dict(m) for m in messages]
    for i in range(len(result) - 1, -1, -1):
        if result[i].get("role") == "user":
            original = result[i].get("content", "")
            text = original if isinstance(original, str) else ""
            result[i]["content"] = [{"type": "text", "text": text}, *image_parts]
            return result

    # No existing user message — append one carrying only the images.
    result.append({"role": "user", "content": [{"type": "text", "text": ""}, *image_parts]})
    return result


def _log_vision_routing(*, task: str, model: str, image_count: int) -> None:
    logger.info(
        "llm_vision_routing",
        task=task,
        model=model,
        image_count=image_count,
        cost_multiplier=VISION_COST_MULTIPLIER,
    )


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
        attached_images: MinIO keys or base64-encoded images — if present,
            routes to the vision model and injects them into the last user
            message as multimodal content parts (ARCH §8.22).

    Returns:
        The assistant's response text.
    """
    settings = get_settings()
    vision = bool(attached_images)
    model = _resolve_vision_model() if vision else _resolve_model(task)
    call_messages: list[dict[str, Any]] = list(messages)
    if vision:
        assert attached_images is not None
        call_messages = inject_images_into_messages(call_messages, attached_images)
        _log_vision_routing(task=task, model=model, image_count=len(attached_images))

    client = _get_client(task)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=call_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.info(
            "llm_chat_complete",
            task=task,
            provider=settings.LLM_PROVIDER,
            model=model,
            vision=vision,
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
    attached_images: list[str] | None = None,
) -> ChatUsage:
    """Like :func:`chat`, but also returns token usage for cost metering.

    Callers enforcing a USD ceiling (framework research) need per-call token
    counts. Usage may be absent from a provider response; missing counts are
    reported as 0 (a conservative under-count is preferable to failing the run).
    ``attached_images`` routes to the vision model exactly as in :func:`chat`.
    """
    settings = get_settings()
    vision = bool(attached_images)
    model = _resolve_vision_model() if vision else _resolve_model(task)
    call_messages: list[dict[str, Any]] = list(messages)
    if vision:
        assert attached_images is not None
        call_messages = inject_images_into_messages(call_messages, attached_images)
        _log_vision_routing(task=task, model=model, image_count=len(attached_images))

    client = _get_client(task)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=call_messages,  # type: ignore[arg-type]
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
            vision=vision,
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
    attached_images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion, yielding text chunks as they arrive.

    ``attached_images`` routes to the vision model exactly as in :func:`chat`.
    """
    settings = get_settings()
    vision = bool(attached_images)
    model = _resolve_vision_model() if vision else _resolve_model(task)
    call_messages: list[dict[str, Any]] = list(messages)
    if vision:
        assert attached_images is not None
        call_messages = inject_images_into_messages(call_messages, attached_images)
        _log_vision_routing(task=task, model=model, image_count=len(attached_images))

    client = _get_client(task)

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=call_messages,  # type: ignore[arg-type]
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
