"""T-131 — voice dictation (STT insert/replace) API tests (school tenant).

Acceptance (M-10 T-131):
1/2. Insert-vs-replace is a frontend TipTap concern (insertContent replaces
     the current selection automatically) — this suite covers what the
     backend owns: transcription itself.
3. STT uses faster-whisper via the single infrastructure.voice.router entry
   point (mocked here — never a raw whisper import).
4. A voice-originated save (used_voice_edit=True) still creates a normal new
   version, annotated "Applied voice edit".
5. en/ur/sd/ps all accepted; anything else rejected by the route's pattern.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureVersion
from app.features.users.models import User, UserAccountStatus, UserRole

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

LECTURE = SchoolLecture(
    id="lecture-1",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Forces",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="version-1",
)

V1 = SchoolLectureVersion(
    id="version-1",
    lecture_id="lecture-1",
    version=1,
    body="Original AI-generated body.",
    content_jsonb=None,
    created_at=datetime.now(timezone.utc),
)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeLectureRepo:
    store: dict[str, SchoolLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return self.store.get(lecture_id)


class _FakeVersionRepo:
    store: dict[str, SchoolLectureVersion] = {}
    created: list[SchoolLectureVersion] = []

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, version_id: str) -> SchoolLectureVersion | None:
        return self.store.get(version_id)

    async def get_latest_for_lecture(self, lecture_id: str) -> SchoolLectureVersion | None:
        rows = [v for v in self.store.values() if v.lecture_id == lecture_id]
        return max(rows, key=lambda v: v.version) if rows else None

    async def create(self, version: SchoolLectureVersion) -> SchoolLectureVersion:
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
    LECTURE.current_version_id = "version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeVersionRepo.store = {V1.id: V1}
    _FakeVersionRepo.created = []
    _transcribe_calls.clear()

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _FakeVersionRepo)
    monkeypatch.setattr("app.features.lectures.service.publish_lecture_event", _FakePublish())
    monkeypatch.setattr("app.features.lectures.service.voice_transcribe", _fake_voice_transcribe)
    # T-134: every save chains a scoring Celery dispatch — never let a unit
    # test touch a real broker.
    monkeypatch.setattr(
        "app.features.lectures.tasks.score_lecture_version.apply_async", MagicMock()
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


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
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    assert res.json()["data"]["transcript"] == "This is the dictated sentence."
    assert len(_transcribe_calls) == 1
    assert _transcribe_calls[0]["audio_bytes"] == b"fake-audio-bytes"
    assert _transcribe_calls[0]["language"] is None


@pytest.mark.parametrize("language", ["en", "ur", "sd", "ps"])
@pytest.mark.asyncio
async def test_transcribe_accepts_all_four_supported_languages(
    client: AsyncClient, language: str
) -> None:
    """Acceptance #5."""
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        params={"language": language},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    assert _transcribe_calls[0]["language"] == language


@pytest.mark.asyncio
async def test_transcribe_rejects_unsupported_language(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        params={"language": "fr"},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0


@pytest.mark.asyncio
async def test_transcribe_rejects_empty_audio(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", b"", "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0


@pytest.mark.asyncio
async def test_transcribe_rejects_oversized_audio(client: AsyncClient) -> None:
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", oversized, "audio/webm")},
    )
    assert res.status_code == 422
    assert len(_transcribe_calls) == 0


@pytest.mark.asyncio
async def test_transcribe_rejected_when_lecture_not_editable(client: AsyncClient) -> None:
    LECTURE.status = LectureStatus.GENERATING
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/voice-transcribe",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_voice_originated_save_creates_normal_version_with_annotation(
    client: AsyncClient,
) -> None:
    """Acceptance #4."""
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
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
    assert data["edit_summary"] is not None
    assert "Applied voice edit" in data["edit_summary"]
    assert len(_FakeVersionRepo.created) == 1


@pytest.mark.asyncio
async def test_text_only_save_has_no_voice_annotation(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Typed content."}]}
                ],
            },
            "is_autosave": False,
            "used_voice_edit": False,
        },
    )
    assert res.status_code == 200
    edit_summary = res.json()["data"]["edit_summary"] or []
    assert "Applied voice edit" not in edit_summary
