"""Tests for the upload pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.files.pipeline import (
    _build_minio_key,
    _validate_magic_bytes,
    list_expired_uploads,
    purge_expired_upload,
)
from app.features.files.profiles import RECOVERY_BUNDLE, get_profile, list_profiles


def test_get_profile_recovery_bundle() -> None:
    profile = get_profile("recovery_bundle")
    assert profile.name == "recovery_bundle"
    assert profile.max_size_bytes == 50 * 1024 * 1024


def test_get_profile_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_profile("nonexistent_profile")


def test_list_profiles_includes_recovery_bundle() -> None:
    assert "recovery_bundle" in list_profiles()


def test_list_profiles_includes_independent_personal_content() -> None:
    assert "independent_personal_content" in list_profiles()


def test_list_profiles_includes_student_question_image() -> None:
    assert "student_question_image" in list_profiles()


def test_get_profile_student_question_image() -> None:
    profile = get_profile("student_question_image")
    assert profile.max_size_bytes == 5 * 1024 * 1024
    assert profile.strip_exif is True
    assert profile.retention_days == 365
    assert "image/webp" in profile.allowed_mime_types
    assert "image/gif" not in profile.allowed_mime_types


def test_get_profile_independent_personal_content() -> None:
    profile = get_profile("independent_personal_content")
    assert profile.max_size_bytes == 100 * 1024 * 1024
    assert profile.bucket == "pdfs"


def test_magic_bytes_valid_pdf() -> None:
    pdf_data = b"%PDF-1.4 rest of file..."
    assert _validate_magic_bytes(pdf_data, RECOVERY_BUNDLE) is True


def test_magic_bytes_invalid_rejects() -> None:
    not_pdf = b"PK\x03\x04rest of zip file"
    assert _validate_magic_bytes(not_pdf, RECOVERY_BUNDLE) is False


def test_minio_key_format() -> None:
    key = _build_minio_key(RECOVERY_BUNDLE, "test.pdf", "upload-123", "school-456")
    assert key.startswith("recovery-bundles/school-456/")
    assert "upload-123" in key
    assert key.endswith("test.pdf")


def test_minio_key_global_scope() -> None:
    key = _build_minio_key(RECOVERY_BUNDLE, "test.pdf", "upload-123", None)
    assert "global" in key


# ---------------------------------------------------------------------------
# T-170 — retention purge helpers (student_question_image 1-year window)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_expired_uploads_queries_by_profile_and_cutoff() -> None:
    session = AsyncMock()
    fake_row = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [fake_row]
    session.execute = AsyncMock(return_value=execute_result)

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    rows = await list_expired_uploads(
        session, profile_name="student_question_image", cutoff=cutoff
    )

    assert rows == [fake_row]
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_purge_expired_upload_deletes_object_and_soft_deletes_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_delete = MagicMock()
    monkeypatch.setattr("app.infrastructure.storage.client.delete_object", mock_delete)

    record = MagicMock()
    record.bucket = "images"
    record.minio_key = "student-question-image/school-1/2025/01/01/u1/a.jpg"
    record.deleted_at = None
    session = AsyncMock()

    await purge_expired_upload(session, record)

    mock_delete.assert_called_once_with(
        "images", "student-question-image/school-1/2025/01/01/u1/a.jpg"
    )
    assert record.deleted_at is not None
    session.commit.assert_awaited_once()
