"""Schema ↔ model alignment (T-230).

A response schema marked ``from_attributes=True`` is a promise that it can be
populated straight off its ORM row. T-230 found ``UploadStatusResponse`` declared
``from_attributes`` while naming the PK ``upload_id`` (the model attribute is
``id``) — so ``model_validate(record)`` would have failed. This test pins the
alignment so the promise holds, and confirms the manual construction path still
works (populate_by_name).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.features.files.models import UploadRecord
from app.features.files.schemas import UploadStatus, UploadStatusResponse


def _make_record() -> UploadRecord:
    return UploadRecord(
        id="upload-abc",
        profile="recovery_bundle",
        filename="notes.pdf",
        size_bytes=1024,
        sha256="0" * 64,
        minio_key="recovery/global/2026/06/06/upload-abc/notes.pdf",
        bucket="uploads",
        status=UploadStatus.READY,
        created_at=datetime.now(timezone.utc),
    )


def test_status_response_validates_from_orm_row() -> None:
    record = _make_record()
    dto = UploadStatusResponse.model_validate(record)
    # upload_id is sourced from record.id via the validation alias.
    assert dto.upload_id == "upload-abc"
    assert dto.status is UploadStatus.READY
    assert dto.filename == "notes.pdf"


def test_status_response_serializes_with_public_field_name() -> None:
    record = _make_record()
    dto = UploadStatusResponse.model_validate(record)
    # The API contract (and generated typed client) keeps the `upload_id` name.
    assert "upload_id" in dto.model_dump()
    assert "id" not in dto.model_dump()


def test_status_response_manual_construction_still_works() -> None:
    dto = UploadStatusResponse(
        upload_id="manual-1",
        status=UploadStatus.PENDING,
        profile="recovery_bundle",
        filename="a.pdf",
        size_bytes=1,
        sha256="0" * 64,
        minio_key="k",
        created_at=datetime.now(timezone.utc),
    )
    assert dto.upload_id == "manual-1"
