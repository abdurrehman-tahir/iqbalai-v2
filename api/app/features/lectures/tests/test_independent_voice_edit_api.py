"""T-131 — voice dictation API tests (independent tenant, mirrors the school suite)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVersion,
    LectureStatus,
)

TEACHER = IndependentUser(
    id="ind-teacher-1",
    authentik_id="auth-ind-teacher",
    email="ind-teacher@example.com",
    display_name="Independent Teacher",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
)

LECTURE = IndependentLecture(
    id="ind-lecture-1",
    teacher_user_id="ind-teacher-1",
    title="Newton's Laws",
    topic="Forces",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ind-version-1",
)

V1 = IndependentLectureVersion(
    id="ind-version-1",
    lecture_id="ind-lecture-1",
    version=1,
    body="Original AI-generated body.",
    content_jsonb=None,
    created_at=datetime.now(timezone.utc),
)


class _FakeUserRepo:
    store: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeLectureRepo:
    store: dict[str, IndependentLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return self.store.get(lecture_id)


class _FakeVersionRepo:
    store: dict[str, IndependentLectureVersion] = {}
    created: list[IndependentLectureVersion] = []

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, version_id: str) -> IndependentLectureVersion | None:
        return self.store.get(version_id)

    async def get_latest_for_lecture(self, lecture_id: str) -> IndependentLectureVersion | None:
        rows = [v for v in self.store.values() if v.lecture_id == lecture_id]
        return max(rows, key=lambda v: v.version) if rows else None

    async def create(self, version: IndependentLectureVersion) -> IndependentLectureVersion:
        if not version.created_at:
            version.created_at = datetime.now(timezone.utc)
        self.store[version.id] = version
        self.__class__.created.append(version)
        return version


class _FakePublish:
    async def __call__(self, *, event_type: str, payload: dict[str, Any]) -> None:
        return None


_transcribe_calls: list[dict[str, Any]] = []


async def _fake_voice_transcribe(audio_bytes: bytes, *, language: str | None = None) -> str:
    _transcribe_calls.append({"audio_bytes": audio_bytes, "language": language})
    return "This is the dictated sentence."


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    LECTURE.current_version_id = "ind-version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeVersionRepo.store = {V1.id: V1}
    _FakeVersionRepo.created = []
    _transcribe_calls.clear()

    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureRepository", _FakeLectureRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureVersionRepository",
        _FakeVersionRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.publish_lecture_event", _FakePublish()
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.voice_transcribe", _fake_voice_transcribe
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-ind-teacher", "role": "independent_teacher", "user_id": "ind-teacher-1"}


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
        "/api/v1/independent/teachers/me/lectures/ind-lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    assert res.json()["data"]["transcript"] == "This is the dictated sentence."


@pytest.mark.asyncio
async def test_voice_originated_save_creates_version_with_annotation(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/independent/teachers/me/lectures/ind-lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Dictated content here."}],
                    }
                ],
            },
            "is_autosave": False,
            "used_voice_edit": True,
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["version"] == 2
    assert "Applied voice edit" in (data["edit_summary"] or [])


@pytest.mark.asyncio
async def test_transcribe_rejects_oversized_audio(client: AsyncClient) -> None:
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    res = await client.post(
        "/api/v1/independent/teachers/me/lectures/ind-lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", oversized, "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0
