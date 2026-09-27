"""T-169 / T-170 — attached_images resolution, tenant isolation, read-model wiring."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.features.student_questions.models import SchoolStudentQuestion
from app.features.student_questions.service import StudentQuestionService, question_to_read
from app.features.users.models import User, UserAccountStatus, UserRole


def _student(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": "stu-1",
        "authentik_id": "auth-1",
        "email": "student@example.com",
        "display_name": "Student One",
        "role": UserRole.STUDENT,
        "status": UserAccountStatus.ACTIVE,
        "school_id": "school-1",
    }
    defaults.update(overrides)
    return User(**defaults)  # type: ignore[arg-type]


def test_question_to_read_includes_attached_images() -> None:
    now = datetime.now(timezone.utc)
    question = SchoolStudentQuestion(
        student_user_id="stu-1",
        session_id="sess-1",
        lecture_id="lec-1",
        question_text="Explain this diagram",
        asked_at=now,
        attached_images_jsonb=[
            {
                "storage_key": "student-question-image/school-1/2026/09/26/u1/a.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 1234,
                "upload_id": "u1",
            }
        ],
    )
    read = question_to_read(question)
    assert len(read.attached_images) == 1
    assert read.attached_images[0].storage_key == (
        "student-question-image/school-1/2026/09/26/u1/a.jpg"
    )
    assert read.attached_images[0].mime_type == "image/jpeg"


def test_question_to_read_empty_attached_images_when_none() -> None:
    now = datetime.now(timezone.utc)
    question = SchoolStudentQuestion(
        student_user_id="stu-1",
        session_id="sess-1",
        lecture_id="lec-1",
        question_text="No image here",
        asked_at=now,
    )
    read = question_to_read(question)
    assert read.attached_images == []


@pytest.mark.asyncio
async def test_resolve_attached_images_empty_list_short_circuits() -> None:
    service = StudentQuestionService(AsyncMock())
    assert await service._resolve_attached_images(_student(), []) == []


@pytest.mark.asyncio
async def test_resolve_attached_images_rejects_more_than_three() -> None:
    service = StudentQuestionService(AsyncMock())
    with pytest.raises(ValidationError, match="Max 3"):
        await service._resolve_attached_images(_student(), ["k1", "k2", "k3", "k4"])


@pytest.mark.asyncio
async def test_resolve_attached_images_rejects_unowned_or_missing_image() -> None:
    service = StudentQuestionService(AsyncMock())
    service._images.get_owned = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(ValidationError, match="not owned"):
        await service._resolve_attached_images(_student(), ["someone-elses-key"])


@pytest.mark.asyncio
async def test_resolve_attached_images_scopes_lookup_by_school_and_owner() -> None:
    service = StudentQuestionService(AsyncMock())
    captured: dict[str, object] = {}

    async def _get_owned(storage_key: str, *, tenant_scope_id: str, uploaded_by: str) -> MagicMock:
        captured["tenant_scope_id"] = tenant_scope_id
        captured["uploaded_by"] = uploaded_by
        record = MagicMock()
        record.minio_key = storage_key
        record.filename = "diagram.jpg"
        record.size_bytes = 1024
        record.id = "upload-1"
        return record

    service._images.get_owned = _get_owned  # type: ignore[method-assign]
    student = _student(school_id="school-9")

    refs = await service._resolve_attached_images(student, ["diagram-key"])

    assert len(refs) == 1
    assert refs[0].storage_key == "diagram-key"
    assert refs[0].mime_type == "image/jpeg"
    assert refs[0].upload_id == "upload-1"
    # Tenant isolation (T-170): scoped by the student's own school_id + id —
    # never another student's or another school's uploads.
    assert captured["tenant_scope_id"] == "school-9"
    assert captured["uploaded_by"] == "stu-1"


@pytest.mark.asyncio
async def test_resolve_attached_images_independent_student_scoped_by_own_user_id() -> None:
    service = StudentQuestionService(AsyncMock())
    captured: dict[str, object] = {}

    async def _get_owned(storage_key: str, *, tenant_scope_id: str, uploaded_by: str) -> MagicMock:
        captured["tenant_scope_id"] = tenant_scope_id
        record = MagicMock()
        record.minio_key = storage_key
        record.filename = "a.png"
        record.size_bytes = 5
        record.id = "u2"
        return record

    service._images.get_owned = _get_owned  # type: ignore[method-assign]
    # Independent student: no school_id — tenant scope must be the student's own id.
    student = _student(id="ind-student-1", school_id=None)

    await service._resolve_attached_images(student, ["k"])

    assert captured["tenant_scope_id"] == "ind-student-1"
