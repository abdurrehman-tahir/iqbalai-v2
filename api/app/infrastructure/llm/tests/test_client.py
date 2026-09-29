"""Tests for LLM client per T-010 acceptance criteria (+ T-168 vision routing)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.client import (
    _looks_like_storage_key,
    _resolve_model,
    _resolve_vision_model,
    _strip_provider_prefix,
    chat,
    chat_with_usage,
    inject_images_into_messages,
    stream_chat,
)

# ---------------------------------------------------------------------------
# _resolve_model — task routing (pure logic, no network)
# ---------------------------------------------------------------------------


def test_resolve_model_falls_back_to_llm_model_for_unknown_task() -> None:
    with patch("app.infrastructure.llm.client.get_settings") as mock_settings:
        s = MagicMock()
        s.LLM_MODEL = "llama-3.1-70b-versatile"
        s.LECTURE_GEN_MODEL = ""
        s.CHATBOT_MODEL = ""
        s.STUDENT_QA_MODEL = ""
        s.VA_MODEL = ""
        s.SCORING_MODEL = ""
        mock_settings.return_value = s

        model = _resolve_model("unknown_task")

    assert model == "llama-3.1-70b-versatile"


def test_resolve_model_returns_override_for_known_task() -> None:
    with patch("app.infrastructure.llm.client.get_settings") as mock_settings:
        s = MagicMock()
        s.LLM_MODEL = "llama-3.1-70b-versatile"
        s.LECTURE_GEN_MODEL = "mixtral-8x7b-32768"
        s.CHATBOT_MODEL = ""
        s.STUDENT_QA_MODEL = ""
        s.VA_MODEL = ""
        s.SCORING_MODEL = ""
        mock_settings.return_value = s

        model = _resolve_model("lecture_generation")

    assert model == "mixtral-8x7b-32768"


def test_resolve_model_falls_back_when_override_empty_string() -> None:
    with patch("app.infrastructure.llm.client.get_settings") as mock_settings:
        s = MagicMock()
        s.LLM_MODEL = "llama-3.1-70b-versatile"
        s.CHATBOT_MODEL = ""
        s.LECTURE_GEN_MODEL = ""
        s.STUDENT_QA_MODEL = ""
        s.VA_MODEL = ""
        s.SCORING_MODEL = ""
        mock_settings.return_value = s

        model = _resolve_model("chatbot")

    assert model == "llama-3.1-70b-versatile"


def test_resolve_model_empty_task_uses_default() -> None:
    with patch("app.infrastructure.llm.client.get_settings") as mock_settings:
        s = MagicMock()
        s.LLM_MODEL = "llama-3.1-70b-versatile"
        s.LECTURE_GEN_MODEL = ""
        s.CHATBOT_MODEL = ""
        s.STUDENT_QA_MODEL = ""
        s.VA_MODEL = ""
        s.SCORING_MODEL = ""
        mock_settings.return_value = s

        model = _resolve_model("")

    assert model == "llama-3.1-70b-versatile"


# ---------------------------------------------------------------------------
# chat() — provider call (mocked AsyncOpenAI)
# ---------------------------------------------------------------------------


def _fake_settings() -> MagicMock:
    s = MagicMock()
    s.LLM_API_KEY = "test-key"
    s.LLM_BASE_URL = "https://api.groq.com/openai/v1"
    s.LLM_MODEL = "llama-3.1-70b-versatile"
    s.LLM_PROVIDER = "groq"
    s.LECTURE_GEN_MODEL = ""
    s.CHATBOT_MODEL = ""
    s.STUDENT_QA_MODEL = ""
    s.VA_MODEL = ""
    s.SCORING_MODEL = ""
    s.LLM_VISION_MODEL = "llama-3.2-90b-vision-preview"
    return s


def _fake_completion(content: str) -> MagicMock:
    """Build a fake OpenAI ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.prompt_tokens = 10
    completion.usage.completion_tokens = 20
    return completion


@pytest.mark.asyncio
async def test_chat_returns_response_text() -> None:
    fake_completion = _fake_completion("Hello from LLM")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        result = await chat([{"role": "user", "content": "Hi"}], task="smoke_test")

    assert result == "Hello from LLM"


@pytest.mark.asyncio
async def test_chat_calls_create_with_correct_model() -> None:
    fake_completion = _fake_completion("ok")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        await chat([{"role": "user", "content": "Hi"}], task="")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.1-70b-versatile"


@pytest.mark.asyncio
async def test_chat_raises_on_provider_error() -> None:
    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("provider down"))
        mock_openai_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="provider down"):
            await chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# Vision routing — attached_images triggers vision logging (ARCH §8.22)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_with_attached_images_still_returns_response() -> None:
    """Vision routing stub: images present, call still completes."""
    fake_completion = _fake_completion("I see an image")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        result = await chat(
            [{"role": "user", "content": "Describe this"}],
            task="student_qa",
            attached_images=["base64encodedimage=="],
        )

    assert result == "I see an image"


# ---------------------------------------------------------------------------
# T-168 — vision-model resolution + provider-prefix stripping
# ---------------------------------------------------------------------------


def test_strip_provider_prefix_removes_groq_prefix() -> None:
    assert _strip_provider_prefix("groq:llama-3.2-90b-vision-preview") == (
        "llama-3.2-90b-vision-preview"
    )


def test_strip_provider_prefix_leaves_bare_model_unchanged() -> None:
    assert _strip_provider_prefix("llama-3.2-90b-vision-preview") == (
        "llama-3.2-90b-vision-preview"
    )


def test_resolve_vision_model_strips_prefix_from_settings() -> None:
    with patch("app.infrastructure.llm.client.get_settings") as mock_settings:
        s = MagicMock()
        s.LLM_VISION_MODEL = "groq:llama-3.2-90b-vision-preview"
        mock_settings.return_value = s

        assert _resolve_vision_model() == "llama-3.2-90b-vision-preview"


# ---------------------------------------------------------------------------
# T-168 — _looks_like_storage_key heuristic (MinIO key vs. base64 blob)
# ---------------------------------------------------------------------------


def test_looks_like_storage_key_true_for_minio_style_path() -> None:
    key = "student-question-image/school-1/2026/09/26/upload-1/diagram.jpg"
    assert _looks_like_storage_key(key) is True


def test_looks_like_storage_key_false_for_base64_blob() -> None:
    # Short base64 fixture with no '/' — clearly not a path.
    assert _looks_like_storage_key("aGVsbG8gd29ybGQ=") is False


def test_looks_like_storage_key_false_for_data_url() -> None:
    assert _looks_like_storage_key("data:image/png;base64,aGVsbG8=") is False


# ---------------------------------------------------------------------------
# T-168 — inject_images_into_messages (multimodal content parts)
# ---------------------------------------------------------------------------


def test_inject_images_into_messages_wraps_last_user_message() -> None:
    messages = [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "What is this diagram?"},
    ]
    with patch(
        "app.infrastructure.llm.client._to_data_url",
        return_value="data:image/jpeg;base64,AAA",
    ):
        result = inject_images_into_messages(messages, ["some-base64=="])

    assert result[0] == messages[0]
    content = result[1]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "What is this diagram?"}
    assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}}
    # Original messages list must not be mutated.
    assert messages[1]["content"] == "What is this diagram?"


def test_inject_images_into_messages_no_images_returns_same_list() -> None:
    messages = [{"role": "user", "content": "hi"}]
    assert inject_images_into_messages(messages, []) is messages


def test_inject_images_into_messages_downloads_minio_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "student-question-image/school-1/2026/09/26/upload-1/diagram.jpg"
    fake_bytes = b"\xff\xd8\xff" + b"0" * 20  # JPEG magic

    monkeypatch.setattr(
        "app.infrastructure.storage.client.download_bytes",
        lambda bucket, k: fake_bytes,
    )

    result = inject_images_into_messages(
        [{"role": "user", "content": "Describe"}],
        [key],
    )
    content = result[0]["content"]
    image_url = content[1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_inject_images_into_messages_treats_non_key_as_base64() -> None:
    result = inject_images_into_messages(
        [{"role": "user", "content": "Describe"}],
        ["QQ=="],
    )
    content = result[0]["content"]
    image_url = content[1]["image_url"]["url"]
    assert image_url == "data:image/jpeg;base64,QQ=="


# ---------------------------------------------------------------------------
# T-168 — chat() / chat_with_usage() / stream_chat() route to the vision model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_routes_to_vision_model_when_images_attached() -> None:
    fake_completion = _fake_completion("I see a force diagram")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        await chat(
            [{"role": "user", "content": "Explain this diagram"}],
            task="student_qa",
            attached_images=["QQ=="],
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.2-90b-vision-preview"
        sent_content = call_kwargs["messages"][0]["content"]
        assert isinstance(sent_content, list)
        assert sent_content[0]["text"] == "Explain this diagram"


@pytest.mark.asyncio
async def test_chat_without_images_routes_to_text_model_unchanged() -> None:
    fake_completion = _fake_completion("plain text answer")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        await chat([{"role": "user", "content": "Plain question"}], task="student_qa")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.1-70b-versatile"
        assert call_kwargs["messages"][0]["content"] == "Plain question"


@pytest.mark.asyncio
async def test_chat_with_usage_routes_to_vision_model_when_images_attached() -> None:
    fake_completion = _fake_completion("vision answer with usage")

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        usage = await chat_with_usage(
            [{"role": "user", "content": "Describe"}],
            task="student_qa",
            attached_images=["QQ=="],
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.2-90b-vision-preview"
        assert usage.text == "vision answer with usage"
        assert usage.total_tokens == 30


@pytest.mark.asyncio
async def test_stream_chat_routes_to_vision_model_when_images_attached() -> None:
    async def _fake_stream() -> Any:
        for text in ("I ", "see ", "a diagram."):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            yield chunk

    with (
        patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()),
        patch("app.infrastructure.llm.client.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())
        mock_openai_cls.return_value = mock_client

        tokens = [
            tok
            async for tok in stream_chat(
                [{"role": "user", "content": "Describe"}],
                task="student_qa",
                attached_images=["QQ=="],
            )
        ]

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.2-90b-vision-preview"
        assert "".join(tokens) == "I see a diagram."
