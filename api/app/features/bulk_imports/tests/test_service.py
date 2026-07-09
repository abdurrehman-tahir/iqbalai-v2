"""Unit tests for bulk import parsing, validation, and commit — T-037/T-079."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

<<<<<<< HEAD
from app.core.exceptions import PreconditionFailedError
from app.features.bulk_imports.models import BulkImport, BulkImportStatus
from app.core.exceptions import ValidationError
=======
from app.core.exceptions import PreconditionFailedError, ValidationError
from app.features.bulk_imports.models import BulkImport, BulkImportStatus
>>>>>>> 872bfebac25c1b798eeccac9cc8292192b39ad43
from app.features.bulk_imports.service import BulkImportService, _parse_csv
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.grades.models import Grade, GradeStatus
from app.features.sections.models import DEFAULT_INTERNAL_NAME, Section, SectionStatus
from app.features.users.models import User, UserRole


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def _coordinator() -> User:
    return User(
        id="coord-1",
        authentik_id="auth-coord",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        school_id="school-1",
        scoped_ids="Grade 9",
    )


def _grade() -> Grade:
    return Grade(
        id="grade-9",
        school_id="school-1",
        name="Grade 9",
        academic_session="2025-2026",
        level_ordinal=9,
        status=GradeStatus.ACTIVE,
    )


def _default_section() -> Section:
    return Section(
        id="default-9",
        grade_id="grade-9",
        name=DEFAULT_INTERNAL_NAME,
        is_default_internal=True,
        status=SectionStatus.ACTIVE,
    )


def _patch_dry_run_deps(svc: BulkImportService, monkeypatch: pytest.MonkeyPatch) -> None:
<<<<<<< HEAD
    monkeypatch.setattr(svc._sessions, "get_school_active_label", AsyncMock(return_value="2025-2026"))
    monkeypatch.setattr(svc._grades, "get_by_name_session", AsyncMock(return_value=_grade()))
    monkeypatch.setattr(svc._sections, "get_by_name", AsyncMock(return_value=None))
    monkeypatch.setattr(svc._sections, "list_by_grade", AsyncMock(return_value=[_default_section()]))
=======
    monkeypatch.setattr(
        svc._sessions, "get_school_active_label", AsyncMock(return_value="2025-2026")
    )
    monkeypatch.setattr(svc._grades, "get_by_name_session", AsyncMock(return_value=_grade()))
    monkeypatch.setattr(svc._sections, "get_by_name", AsyncMock(return_value=None))
    monkeypatch.setattr(
        svc._sections, "list_by_grade", AsyncMock(return_value=[_default_section()])
    )
>>>>>>> 872bfebac25c1b798eeccac9cc8292192b39ad43
    monkeypatch.setattr(svc._invites, "get_pending_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(svc._independent_users, "get_by_email", AsyncMock(return_value=None))


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
    _patch_dry_run_deps(svc, pytest.MonkeyPatch())

    csv = _csv_bytes(
        "name,email,grade\n" "Valid,valid@test.com,Grade 9\n" "Bad Grade,bad@test.com,Grade 10\n"
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
        patch.object(svc._users, "get_by_authentik_id", return_value=_coordinator()),
        patch.object(svc._users, "get_by_email", return_value=None),
        patch("app.features.bulk_imports.service.run_upload_pipeline", return_value=upload_result),
        patch.object(svc._repo, "save", side_effect=_fake_save),
        patch("app.features.bulk_imports.service.audit", AsyncMock()),
        patch.object(svc._sessions, "get_school_active_label", AsyncMock(return_value="2025-2026")),
        patch.object(svc._grades, "get_by_name_session", AsyncMock(return_value=_grade())),
        patch.object(svc._sections, "list_by_grade", AsyncMock(return_value=[_default_section()])),
        patch.object(svc._invites, "get_pending_by_email", AsyncMock(return_value=None)),
        patch.object(svc._independent_users, "get_by_email", AsyncMock(return_value=None)),
    ):
        result = await svc.dry_run(
            data=csv, filename="students.csv", actor_authentik_id="auth-coord"
        )

    assert result.total_rows == 2
    assert result.success_rows == 1
    assert result.failed_rows == 1
    invalid = next(r for r in result.rows if r.status == "invalid")
    assert "grade_out_of_scope" in invalid.errors
    assert invalid.data is not None
    assert invalid.data.get("grade_id") == ""


@pytest.mark.asyncio
async def test_dry_run_detects_duplicate_email_in_file() -> None:
    mock_session = AsyncMock()
    svc = BulkImportService(mock_session)

<<<<<<< HEAD
    csv = _csv_bytes(
        "name,email,grade\n"
        "One,dup@test.com,Grade 9\n"
        "Two,dup@test.com,Grade 9\n"
    )
=======
    csv = _csv_bytes("name,email,grade\n" "One,dup@test.com,Grade 9\n" "Two,dup@test.com,Grade 9\n")
>>>>>>> 872bfebac25c1b798eeccac9cc8292192b39ad43
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
        patch.object(svc._users, "get_by_authentik_id", return_value=_coordinator()),
        patch.object(svc._users, "get_by_email", return_value=None),
        patch("app.features.bulk_imports.service.run_upload_pipeline", return_value=upload_result),
        patch.object(svc._repo, "save", side_effect=_fake_save),
        patch("app.features.bulk_imports.service.audit", AsyncMock()),
        patch.object(svc._sessions, "get_school_active_label", AsyncMock(return_value="2025-2026")),
        patch.object(svc._grades, "get_by_name_session", AsyncMock(return_value=_grade())),
        patch.object(svc._sections, "list_by_grade", AsyncMock(return_value=[_default_section()])),
        patch.object(svc._invites, "get_pending_by_email", AsyncMock(return_value=None)),
        patch.object(svc._independent_users, "get_by_email", AsyncMock(return_value=None)),
    ):
        result = await svc.dry_run(
            data=csv, filename="students.csv", actor_authentik_id="auth-coord"
        )

    dup_row = next(r for r in result.rows if r.row_number == 3)
    assert "duplicate_email_in_file" in dup_row.errors


@pytest.mark.asyncio
async def test_commit_enrolls_valid_rows_partial_success() -> None:
    mock_session = AsyncMock()
    svc = BulkImportService(mock_session)
    job = BulkImport(
        id="job-1",
        school_id="school-1",
        imported_by_user_id="coord-1",
        upload_id="upload-1",
        total_rows=2,
        success_rows=1,
        failed_rows=1,
        error_report_jsonb={
            "rows": [
                {
                    "row_number": 2,
                    "status": "valid",
                    "errors": [],
                    "data": {
                        "name": "Alice",
                        "email": "alice@test.com",
                        "grade": "Grade 9",
                        "section": "",
                        "language": "en",
                        "grade_id": "grade-9",
                        "section_id": "default-9",
                    },
                },
                {
                    "row_number": 3,
                    "status": "invalid",
                    "errors": ["grade_out_of_scope"],
                    "data": {"name": "Bob", "email": "bob@test.com", "grade": "Grade 10"},
                },
            ]
        },
        status=BulkImportStatus.DRY_RUN_COMPLETE,
        completed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )

    enroll_mock = AsyncMock()
    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=_coordinator()),
        patch.object(svc._repo, "get_by_id_for_school", return_value=job),
        patch.object(svc._repo, "update", side_effect=lambda j: j),
        patch.object(svc, "_session", mock_session),
        patch("app.features.bulk_imports.service.StudentEnrollmentService") as enrollment_cls,
        patch("app.features.bulk_imports.service.audit", AsyncMock()),
        patch("app.features.bulk_imports.service.notify_account_event", AsyncMock()),
    ):
        enrollment_cls.return_value.enroll_student = enroll_mock
        result = await svc.commit(
            "job-1",
            "auth-coord",
            {"sub": "auth-coord", "role": "coordinator", "school_id": "school-1"},
        )

    enroll_mock.assert_called_once()
    assert result.status == BulkImportStatus.COMMITTED_WITH_ERRORS.value
    assert result.success_rows == 1
    assert result.failed_rows == 1
    enrolled = next(r for r in result.rows if r.row_number == 2)
    assert enrolled.status == "enrolled"


@pytest.mark.asyncio
async def test_commit_rejects_already_committed_job() -> None:
    mock_session = AsyncMock()
    svc = BulkImportService(mock_session)
    job = BulkImport(
        id="job-1",
        school_id="school-1",
        imported_by_user_id="coord-1",
        upload_id="upload-1",
        total_rows=1,
        success_rows=1,
        failed_rows=0,
        error_report_jsonb={"rows": []},
        status=BulkImportStatus.COMMITTED,
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=_coordinator()),
        patch.object(svc._repo, "get_by_id_for_school", return_value=job),
    ):
        with pytest.raises(PreconditionFailedError, match="not ready to commit"):
            await svc.commit("job-1", "auth-coord", {"sub": "auth-coord"})
