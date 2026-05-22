"""Tests for LLM client per T-010 acceptance criteria."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.client import _resolve_model, chat


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

    with patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()), patch(
        "app.infrastructure.llm.client.AsyncOpenAI"
    ) as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        result = await chat([{"role": "user", "content": "Hi"}], task="smoke_test")

    assert result == "Hello from LLM"


@pytest.mark.asyncio
async def test_chat_calls_create_with_correct_model() -> None:
    fake_completion = _fake_completion("ok")

    with patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()), patch(
        "app.infrastructure.llm.client.AsyncOpenAI"
    ) as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        await chat([{"role": "user", "content": "Hi"}], task="")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.1-70b-versatile"


@pytest.mark.asyncio
async def test_chat_raises_on_provider_error() -> None:
    with patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()), patch(
        "app.infrastructure.llm.client.AsyncOpenAI"
    ) as mock_openai_cls:
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

    with patch("app.infrastructure.llm.client.get_settings", return_value=_fake_settings()), patch(
        "app.infrastructure.llm.client.AsyncOpenAI"
    ) as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_completion)
        mock_openai_cls.return_value = mock_client

        result = await chat(
            [{"role": "user", "content": "Describe this"}],
            task="student_qa",
            attached_images=["base64encodedimage=="],
        )

    assert result == "I see an image"
