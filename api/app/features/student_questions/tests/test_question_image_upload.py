"""T-166 — student_question_image profile + ingest tests."""

from __future__ import annotations

import io
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.files.pipeline import (
    _validate_magic_bytes,
    strip_exif_metadata,
)
from app.features.files.profiles import (
    STUDENT_QUESTION_IMAGE,
    STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION,
    get_profile,
    list_profiles,
)
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.users.models import User, UserAccountStatus, UserRole

# Minimal JPEG (1x1) with EXIF-ish APP1 marker for strip tests.
_JPEG_SOI = b"\xff\xd8\xff"
# Minimal valid-enough JPEG for magic checks (not a full parseable image for PIL —
# strip tests use a Pillow-generated buffer).
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_GIF87 = b"GIF87a"
_WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


def _make_jpeg_with_exif() -> bytes:
    """Build a tiny JPEG that includes an EXIF APP1 segment via Pillow."""
    from PIL import Image

    img = Image.new("RGB", (8, 8), color=(10, 20, 30))
    # Pillow accepts exif= as bytes for JPEG save in recent versions.
    buf = io.BytesIO()
    exif = img.getexif()
    exif[271] = "IqbalAI-Test-Camera"  # Make
    img.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


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


class _FakeSession:
    records: dict[str, Any] = {}
    audit_entries: list[Any] = []

    async def get(self, model: type, pk: str) -> Any:
        return self.records.get(pk)

    async def commit(self) -> None:
        return None

    def add(self, obj: Any) -> None:
        self.audit_entries.append(obj)


_pipeline_calls: list[dict[str, Any]] = []


async def _fake_run_upload_pipeline(**kwargs: Any) -> UploadInitiated:
    from app.features.files.models import UploadRecord

    _pipeline_calls.append(kwargs)
    # Simulate EXIF-stripped smaller payload recorded by pipeline.
    data = kwargs.get("data") or b""
    record = UploadRecord(
        id="upload-sqi-1",
        profile="student_question_image",
        filename=kwargs.get("filename") or "img.jpg",
        size_bytes=len(data) if isinstance(data, (bytes, bytearray)) else 10,
        sha256="a" * 64,
        minio_key=f"student-question-image/{kwargs.get('school_id')}/2026/09/upload-sqi-1/img.jpg",
        bucket="images",
        school_id=kwargs.get("school_id"),
        uploaded_by=kwargs.get("uploaded_by"),
        status=UploadStatus.READY,
    )
    _FakeSession.records[record.id] = record
    return UploadInitiated(
        upload_id=record.id, status=UploadStatus.READY, status_url="/api/v1/uploads/upload-sqi-1"
    )


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    _FakeSession.records = {}
    _FakeSession.audit_entries = []
    _pipeline_calls.clear()
    monkeypatch.setattr("app.features.student_questions.image_upload.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.student_questions.image_upload.run_upload_pipeline",
        _fake_run_upload_pipeline,
    )


async def _fake_db() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


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


def test_student_question_image_profile_registered() -> None:
    assert "student_question_image" in list_profiles()
    profile = get_profile("student_question_image")
    assert profile is STUDENT_QUESTION_IMAGE
    assert profile.max_size_bytes == 5 * 1024 * 1024
    assert profile.allowed_mime_types == frozenset({"image/jpeg", "image/png", "image/webp"})
    assert profile.strip_exif is True
    assert profile.retention_days == 365
    assert profile.bucket == "images"
    assert STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION == 3


def test_magic_accepts_jpeg_png_webp_rejects_gif() -> None:
    assert _validate_magic_bytes(_JPEG_SOI + b"rest", STUDENT_QUESTION_IMAGE) is True
    assert _validate_magic_bytes(_PNG_MAGIC + b"rest", STUDENT_QUESTION_IMAGE) is True
    assert _validate_magic_bytes(_WEBP, STUDENT_QUESTION_IMAGE) is True
    assert _validate_magic_bytes(_GIF87 + b"rest", STUDENT_QUESTION_IMAGE) is False
    assert _validate_magic_bytes(b"not-an-image", STUDENT_QUESTION_IMAGE) is False


def test_strip_exif_removes_camera_make() -> None:
    original = _make_jpeg_with_exif()
    from PIL import Image

    with Image.open(io.BytesIO(original)) as before:
        assert before.getexif().get(271) == "IqbalAI-Test-Camera"

    cleaned = strip_exif_metadata(original)
    with Image.open(io.BytesIO(cleaned)) as after:
        assert after.getexif().get(271) is None


@pytest.mark.asyncio
async def test_upload_question_image_returns_minio_key(client: AsyncClient) -> None:
    jpeg = _make_jpeg_with_exif()
    res = await client.post(
        "/api/v1/students/me/question-images",
        files={"image": ("diagram.jpg", jpeg, "image/jpeg")},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["upload_id"] == "upload-sqi-1"
    assert data["storage_key"].startswith("student-question-image/school-1/")
    assert data["mime_type"] == "image/jpeg"
    assert data["retention_days"] == 365
    assert len(_pipeline_calls) == 1
    assert _pipeline_calls[0]["school_id"] == "school-1"
    assert _pipeline_calls[0]["profile"].name == "student_question_image"


@pytest.mark.asyncio
async def test_upload_question_image_writes_audit_entry(client: AsyncClient) -> None:
    """T-171 — every image upload is audit-logged (STUDENT_QUESTION_IMAGE_UPLOADED)."""
    from app.features.audit.actions import STUDENT_QUESTION_IMAGE_UPLOADED

    jpeg = _make_jpeg_with_exif()
    res = await client.post(
        "/api/v1/students/me/question-images",
        files={"image": ("diagram.jpg", jpeg, "image/jpeg")},
    )
    assert res.status_code == 201
    assert len(_FakeSession.audit_entries) == 1
    entry = _FakeSession.audit_entries[0]
    assert entry.action == STUDENT_QUESTION_IMAGE_UPLOADED
    assert entry.actor_id == "student-1"
    assert entry.school_id == "school-1"


@pytest.mark.asyncio
async def test_upload_rejects_gif(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/students/me/question-images",
        files={"image": ("anim.gif", _GIF87 + b"xxxx", "image/gif")},
    )
    assert res.status_code == 422
    assert len(_pipeline_calls) == 0


@pytest.mark.asyncio
async def test_upload_rejects_when_already_three_attached(client: AsyncClient) -> None:
    jpeg = _make_jpeg_with_exif()
    res = await client.post(
        "/api/v1/students/me/question-images?already_attached=3",
        files={"image": ("diagram.jpg", jpeg, "image/jpeg")},
    )
    assert res.status_code == 422
    assert "Max 3" in res.json()["error"]["message"]
    assert len(_pipeline_calls) == 0


@pytest.mark.asyncio
async def test_upload_rejects_oversized(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _reject(**kwargs: Any) -> UploadInitiated:
        raise ValueError("File size 6000000 bytes exceeds limit of 5242880 bytes")

    monkeypatch.setattr("app.features.student_questions.image_upload.run_upload_pipeline", _reject)
    res = await client.post(
        "/api/v1/students/me/question-images",
        files={"image": ("huge.jpg", _JPEG_SOI + b"0" * 100, "image/jpeg")},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_independent_student_scoped_to_user_id(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    independent = User(
        id="ind-student-1",
        authentik_id="auth-ind",
        email="ind@example.com",
        display_name="Independent",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
        school_id=None,
    )
    _FakeUserRepo.store = {independent.id: independent}

    async def _ind_user() -> dict[str, object]:
        return {"sub": "auth-ind", "role": "student", "user_id": "ind-student-1"}

    # Override on the app created by the fixture — re-bind via client app.
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_current_user] = _ind_user

    jpeg = _make_jpeg_with_exif()
    res = await client.post(
        "/api/v1/students/me/question-images",
        files={"image": ("diagram.jpg", jpeg, "image/jpeg")},
    )
    assert res.status_code == 201
    assert _pipeline_calls[0]["school_id"] == "ind-student-1"
    assert res.json()["data"]["storage_key"].startswith("student-question-image/ind-student-1/")
