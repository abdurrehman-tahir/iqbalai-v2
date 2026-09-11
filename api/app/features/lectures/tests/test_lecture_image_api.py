"""T-132 — image upload + serve + AI diagram suggestion API tests (school tenant).

Acceptance (M-10 T-132):
1. Drag-drop image -> uploaded via lecture_image profile -> URL inserted (frontend)
2. Upload respects the profile's size/type limits
3. AI surfaces a diagram suggestion when a relevant chunk exists
4. Accepting inserts the referenced diagram; declining is a pure frontend no-op
5. Image insert produces a new version like any other edit (covered by
   test_lecture_version_save_api.py's extra_annotations mechanism — not
   re-tested here since T-132 doesn't add its own save-path fork)
"""

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
from app.features.files.models import UploadRecord
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.lectures.images import DiagramRenderError
from app.features.lectures.models import LectureStatus, SchoolLecture
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

UPLOAD_RECORD = UploadRecord(
    id="upload-1",
    profile="lecture_image",
    filename="diagram.png",
    size_bytes=10,
    sha256="a" * 64,
    minio_key="lecture-image/school-1/2026/09/upload-1/diagram.png",
    bucket="images",
    school_id="school-1",
    uploaded_by="teacher-1",
    status=UploadStatus.READY,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
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


class _FakeSession:
    """Minimal stand-in for AsyncSession.get(), used by get_lecture_image."""

    records: dict[str, UploadRecord] = {}

    async def get(self, model: type, pk: str) -> Any:
        if model is UploadRecord:
            return self.records.get(pk)
        return None


_upload_pipeline_calls: list[dict[str, Any]] = []


async def _fake_run_upload_pipeline(**kwargs: Any) -> UploadInitiated:
    _upload_pipeline_calls.append(kwargs)
    return UploadInitiated(upload_id="upload-1", status=UploadStatus.READY, status_url="/x")


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    LECTURE.current_version_id = "version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeSession.records = {"upload-1": UPLOAD_RECORD}
    _upload_pipeline_calls.clear()

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr(
        "app.features.lectures.service.run_upload_pipeline", _fake_run_upload_pipeline
    )
    monkeypatch.setattr(
        "app.features.lectures.service.download_bytes", lambda bucket, key: b"fake-bytes"
    )


async def _fake_db() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


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
async def test_upload_lecture_image_returns_servable_url(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/images",
        files={"image": ("diagram.png", b"\x89PNG\r\n\x1a\nfakepngdata", "image/png")},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["image_id"] == "upload-1"
    assert data["image_url"] == "/api/v1/teachers/me/lectures/lecture-1/images/upload-1"
    assert len(_upload_pipeline_calls) == 1
    assert _upload_pipeline_calls[0]["school_id"] == "school-1"


@pytest.mark.asyncio
async def test_upload_lecture_image_rejects_oversized_or_wrong_type(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance #2 — size/type limits enforced by the shared pipeline."""

    async def _reject(**kwargs: Any) -> UploadInitiated:
        raise ValueError("File size 6000000 bytes exceeds limit of 5242880 bytes")

    monkeypatch.setattr("app.features.lectures.service.run_upload_pipeline", _reject)
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/images",
        files={"image": ("huge.png", b"\x89PNG" + b"0" * 100, "image/png")},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_rejected_when_lecture_not_editable(client: AsyncClient) -> None:
    LECTURE.status = LectureStatus.GENERATING
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/images",
        files={"image": ("diagram.png", b"\x89PNG\r\n\x1a\nfakepngdata", "image/png")},
    )
    assert res.status_code == 422
    assert len(_upload_pipeline_calls) == 0


@pytest.mark.asyncio
async def test_get_lecture_image_serves_bytes_with_content_type(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/images/upload-1")
    assert res.status_code == 200
    assert res.content == b"fake-bytes"
    assert res.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_get_lecture_image_404s_for_unknown_id(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/images/does-not-exist")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_lecture_image_404s_for_wrong_profile(client: AsyncClient) -> None:
    _FakeSession.records["other-1"] = UploadRecord(
        id="other-1",
        profile="school_library_content",
        filename="ref.pdf",
        size_bytes=10,
        sha256="b" * 64,
        minio_key="k",
        bucket="pdfs",
        school_id="school-1",
        uploaded_by="teacher-1",
        status=UploadStatus.READY,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/images/other-1")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_diagram_suggestions_empty_when_no_v1_paragraphs(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _NoVersionRepo:
        def __init__(self, session: Any) -> None:
            pass

        async def get_first_for_lecture(self, lecture_id: str) -> None:
            return None

    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _NoVersionRepo)
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/diagram-suggestions")
    assert res.status_code == 200
    assert res.json()["data"]["suggestions"] == []


@pytest.mark.asyncio
async def test_accept_diagram_suggestion_renders_and_uploads(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance #4 — accepting inserts the referenced diagram."""

    class _FakeLibraryItem:
        id = "lib-1"
        school_id = "school-1"
        title = "Physics 101"
        storage_key = "school-library/school-1/2026/01/lib-1/book.pdf"

    class _FakeLibraryRepo:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, item_id: str) -> Any:
            return _FakeLibraryItem() if item_id == "lib-1" else None

    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr(
        "app.features.lectures.service.render_pdf_page_to_png", lambda pdf, page: b"rendered-png"
    )

    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/diagram-suggestions/accept",
        json={"library_item_id": "lib-1", "page_number": 34},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["image_id"] == "upload-1"
    assert len(_upload_pipeline_calls) == 1
    assert _upload_pipeline_calls[0]["data"] == b"rendered-png"


@pytest.mark.asyncio
async def test_accept_diagram_suggestion_render_failure_is_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeLibraryItem:
        id = "lib-1"
        school_id = "school-1"
        title = "Physics 101"
        storage_key = "k"

    class _FakeLibraryRepo:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, item_id: str) -> Any:
            return _FakeLibraryItem()

    def _fail_render(pdf: bytes, page: int) -> bytes:
        raise DiagramRenderError("Page 999 is out of range (book has 10 pages)")

    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr("app.features.lectures.service.render_pdf_page_to_png", _fail_render)

    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/diagram-suggestions/accept",
        json={"library_item_id": "lib-1", "page_number": 999},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_accept_diagram_suggestion_unknown_book_is_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeLibraryRepo:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, item_id: str) -> Any:
            return None

    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/diagram-suggestions/accept",
        json={"library_item_id": "does-not-exist", "page_number": 1},
    )
    assert res.status_code == 404
