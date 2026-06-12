"""Unit tests for bulk import parsing and validation — T-037."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.features.bulk_imports.models import BulkImport
from app.core.exceptions import ValidationError
from app.features.bulk_imports.service import BulkImportService, _parse_csv
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.users.models import User, UserRole


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def test_parse_csv_requires_columns() -> None:
    with pytest.raises(ValidationError, match="Missing required columns"):
        _parse_csv(_csv_bytes("foo,bar\n1,2"))


def test_parse_csv_normalizes_headers() -> None:
    rows = _parse_csv(_csv_bytes("Name,Email,Grade,Section\nAlice,a@test.com,Grade 9,A\n"))
    assert rows == [
        {
            "name": "Alice",
            "email": "a@test.com",
            "grade": "Grade 9",
            "section": "A",
            "language": "",
        }
    ]


@pytest.mark.asyncio
async def test_dry_run_flags_out_of_scope_grade() -> None:
    mock_session = AsyncMock()
    svc = BulkImportService(mock_session)

    coordinator = User(
        id="coord-1",
        authentik_id="auth-coord",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        school_id="school-1",
        scoped_ids="Grade 9",
    )
    csv = _csv_bytes(
        "name,email,grade\n"
        "Valid,valid@test.com,Grade 9\n"
        "Bad Grade,bad@test.com,Grade 10\n"
    )
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )
    async def _fake_save(job: BulkImport) -> BulkImport:
        job.created_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        return job

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=coordinator),
        patch.object(svc._users, "get_by_email", return_value=None),
        patch("app.features.bulk_imports.service.run_upload_pipeline", return_value=upload_result),
        patch.object(svc._repo, "save", side_effect=_fake_save),
        patch("app.features.bulk_imports.service.audit", return_value=None),
    ):
        result = await svc.dry_run(data=csv, filename="students.csv", actor_authentik_id="auth-coord")

    assert result.total_rows == 2
    assert result.success_rows == 1
    assert result.failed_rows == 1
    invalid = next(r for r in result.rows if r.status == "invalid")
    assert "grade_out_of_scope" in invalid.errors


@pytest.mark.asyncio
async def test_dry_run_detects_duplicate_email_in_file() -> None:
    mock_session = AsyncMock()
    svc = BulkImportService(mock_session)

    coordinator = User(
        id="coord-1",
        authentik_id="auth-coord",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        school_id="school-1",
        scoped_ids="Grade 9",
    )
    csv = _csv_bytes(
        "name,email,grade\n"
        "One,dup@test.com,Grade 9\n"
        "Two,dup@test.com,Grade 9\n"
    )
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )

    async def _fake_save(job: BulkImport) -> BulkImport:
        job.created_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        return job

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=coordinator),
        patch.object(svc._users, "get_by_email", return_value=None),
        patch("app.features.bulk_imports.service.run_upload_pipeline", return_value=upload_result),
        patch.object(svc._repo, "save", side_effect=_fake_save),
        patch("app.features.bulk_imports.service.audit", return_value=None),
    ):
        result = await svc.dry_run(data=csv, filename="students.csv", actor_authentik_id="auth-coord")

    dup_row = next(r for r in result.rows if r.row_number == 3)
    assert "duplicate_email_in_file" in dup_row.errors
