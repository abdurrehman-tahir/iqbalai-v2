"""T-132 — image upload + serve API tests (independent tenant).

No AI diagram suggestion for independent teachers (school-tenant only,
documented in independent_service.py's upload_lecture_image docstring).
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
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.lectures.models import IndependentLecture, LectureStatus

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


class _FakeSession:
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
    LECTURE.current_version_id = "ind-version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeSession.records = {
        "upload-1": UploadRecord(
            id="upload-1",
            profile="lecture_image",
            filename="diagram.png",
            size_bytes=10,
            sha256="a" * 64,
            minio_key="k",
            bucket="images",
            school_id="ind-teacher-1",  # independent: school_id column holds the user's own id
            uploaded_by="ind-teacher-1",
            status=UploadStatus.READY,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    }
    _upload_pipeline_calls.clear()

    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureRepository", _FakeLectureRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.run_upload_pipeline",
        _fake_run_upload_pipeline,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.download_bytes",
        lambda bucket, key: b"fake-bytes",
    )


async def _fake_db() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


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
async def test_upload_lecture_image_scoped_to_own_user_id(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/independent/teachers/me/lectures/ind-lecture-1/images",
        files={"image": ("diagram.png", b"\x89PNG\r\n\x1a\nfakepngdata", "image/png")},
    )
    assert res.status_code == 200
    assert (
        res.json()["data"]["image_url"]
        == "/api/v1/independent/teachers/me/lectures/ind-lecture-1/images/upload-1"
    )
    assert _upload_pipeline_calls[0]["school_id"] == "ind-teacher-1"


@pytest.mark.asyncio
async def test_get_lecture_image_serves_bytes(client: AsyncClient) -> None:
    res = await client.get("/api/v1/independent/teachers/me/lectures/ind-lecture-1/images/upload-1")
    assert res.status_code == 200
    assert res.content == b"fake-bytes"
    assert res.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_no_diagram_suggestion_route_for_independent_tenant(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/independent/teachers/me/lectures/ind-lecture-1/diagram-suggestions"
    )
    assert res.status_code == 404
