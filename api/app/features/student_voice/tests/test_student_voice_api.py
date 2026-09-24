"""T-155 — student voice STT API tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.users.models import User, UserAccountStatus, UserRole

STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


_transcribe_calls: list[dict[str, Any]] = []


async def _fake_voice_transcribe(audio_bytes: bytes, *, language: str | None = None) -> str:
    _transcribe_calls.append({"audio_bytes": audio_bytes, "language": language})
    return "What is Newton's second law?"


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    _transcribe_calls.clear()
    monkeypatch.setattr("app.features.student_voice.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.student_voice.service.voice_transcribe", _fake_voice_transcribe
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-student", "role": "student", "user_id": "student-1"}


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_transcribe_returns_transcript(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/students/me/voice/transcribe",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    assert res.json()["data"]["transcript"] == "What is Newton's second law?"
    assert len(_transcribe_calls) == 1
    assert _transcribe_calls[0]["audio_bytes"] == b"fake-audio-bytes"
    assert _transcribe_calls[0]["language"] is None


@pytest.mark.parametrize("language", ["en", "ur", "sd", "ps"])
@pytest.mark.asyncio
async def test_transcribe_accepts_supported_languages(client: AsyncClient, language: str) -> None:
    res = await client.post(
        "/api/v1/students/me/voice/transcribe",
        params={"language": language},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    assert _transcribe_calls[0]["language"] == language


@pytest.mark.asyncio
async def test_transcribe_rejects_unsupported_language(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/students/me/voice/transcribe",
        params={"language": "fr"},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0


@pytest.mark.asyncio
async def test_transcribe_rejects_empty_audio(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/students/me/voice/transcribe",
        files={"audio": ("clip.webm", b"", "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0


@pytest.mark.asyncio
async def test_transcribe_rejects_oversized_audio(client: AsyncClient) -> None:
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    res = await client.post(
        "/api/v1/students/me/voice/transcribe",
        files={"audio": ("clip.webm", oversized, "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0
