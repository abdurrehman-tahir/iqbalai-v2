"""Unit tests for independent private pool service — T-074."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import PermissionDeniedError
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.library.independent_personal_models import (
    IndependentPersonalContent,
    PersonalContentStatus,
    PersonalContentType,
    PersonalStructuredParsingStatus,
)
from app.features.library.independent_personal_schemas import IndependentPersonalUploadRequest
from app.features.library.independent_personal_service import IndependentPersonalContentService


def _independent_user(**kwargs: object) -> IndependentUser:
    user = IndependentUser(
        id="user-1",
        authentik_id="auth-1",
        email="user@example.com",
        display_name="User One",
        role=IndependentUserRole.INDEPENDENT_TEACHER,
        status=IndependentUserAccountStatus.ACTIVE,
        language_preference="en",
    )
    for key, value in kwargs.items():
        setattr(user, key, value)
    return user


def _content(**kwargs: object) -> IndependentPersonalContent:
    item = IndependentPersonalContent(
        id="content-1",
        user_id="user-1",
        content_type=PersonalContentType.REFERENCE,
        title="My Notes",
        file_key="independent-personal/user-1/file.pdf",
        file_sha256="a" * 64,
        status=PersonalContentStatus.PENDING,
        structured_parsing_status=PersonalStructuredParsingStatus.NOT_APPLICABLE,
        vector_collection="independent_personal_user-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for key, value in kwargs.items():
        setattr(item, key, value)
    return item


@pytest.mark.asyncio
async def test_upload_deduplicates_per_user() -> None:
    mock_session = AsyncMock()
    svc = IndependentPersonalContentService(mock_session)
    user = _independent_user()
    existing = _content(status=PersonalContentStatus.AVAILABLE)
    meta = IndependentPersonalUploadRequest(title="My Notes")

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=user),
        patch.object(svc._repo, "get_by_user_sha256", return_value=existing),
        patch("app.features.library.independent_personal_service.audit", return_value=None),
        patch(
            "app.features.library.independent_personal_tasks.ingest_independent_personal_content.apply_async"
        ) as mock_task,
    ):
        result = await svc.upload(
            data=b"%PDF-fake",
            filename="notes.pdf",
            meta=meta,
            authentik_id="auth-1",
        )

    assert result.storage_deduplicated is True
    assert result.item.id == existing.id
    mock_task.assert_not_called()


@pytest.mark.asyncio
async def test_upload_creates_content_and_queues_ingestion() -> None:
    mock_session = AsyncMock()
    svc = IndependentPersonalContentService(mock_session)
    user = _independent_user()
    saved = _content(id="content-new")
    meta = IndependentPersonalUploadRequest(title="Fresh Notes")
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )

    mock_upload_record = AsyncMock()
    mock_upload_record.minio_key = "independent-personal/user-1/new.pdf"
    mock_upload_record.deleted_at = None

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=user),
        patch.object(svc._repo, "get_by_user_sha256", return_value=None),
        patch.object(svc._repo, "save", return_value=saved),
        patch(
            "app.features.library.independent_personal_service.sha256_of_bytes",
            return_value="b" * 64,
        ),
        patch(
            "app.features.library.independent_personal_service.run_upload_pipeline",
            return_value=upload_result,
        ),
        patch.object(mock_session, "get", return_value=mock_upload_record),
        patch("app.features.library.independent_personal_service.audit", return_value=None),
        patch(
            "app.features.library.independent_personal_tasks.ingest_independent_personal_content.apply_async"
        ) as mock_task,
    ):
        result = await svc.upload(
            data=b"%PDF-new",
            filename="new.pdf",
            meta=meta,
            authentik_id="auth-1",
        )

    assert result.storage_deduplicated is False
    assert result.item.id == saved.id
    mock_task.assert_called_once()


@pytest.mark.asyncio
async def test_school_teacher_cannot_access_private_pool() -> None:
    mock_session = AsyncMock()
    svc = IndependentPersonalContentService(mock_session)

    with pytest.raises(PermissionDeniedError):
        await svc.list_items({"sub": "teacher-1", "role": "teacher", "tenant_type": "school"})
