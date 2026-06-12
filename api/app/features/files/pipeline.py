"""Single parametrized upload pipeline per ARCH §11.2."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.files.models import UploadRecord
from app.features.files.profiles import UploadProfile
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.infrastructure.storage.client import sha256_of_bytes, upload_bytes

logger = structlog.get_logger(__name__)


def _build_minio_key(
    profile: UploadProfile, filename: str, upload_id: str, school_id: str | None
) -> str:
    """Build the MinIO object key per ARCH §11.4 strategy.

    Format: {key_prefix}/{school_id or 'global'}/{date}/{upload_id}/{filename}
    """
    date_part = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    scope = school_id or "global"
    return f"{profile.key_prefix}/{scope}/{date_part}/{upload_id}/{filename}"


def _validate_magic_bytes(data: bytes, profile: UploadProfile) -> bool:
    """Check that the file starts with one of the expected magic byte sequences."""
    if not profile.magic_bytes:
        return True
    return any(data[: len(magic)] == magic for magic in profile.magic_bytes)


async def run_upload_pipeline(
    data: bytes,
    filename: str,
    profile: UploadProfile,
    session: AsyncSession,
    school_id: str | None = None,
    uploaded_by: str | None = None,
    *,
    skip_magic_check: bool = False,
) -> UploadInitiated:
    """Execute the upload pipeline for a file.

    Steps: validate magic bytes → check size → dedup (SHA-256) → upload to MinIO → record in DB.
    Returns UploadInitiated immediately (202 Accepted pattern).
    """
    # 1. Magic-byte validation
    if not skip_magic_check and not _validate_magic_bytes(data, profile):
        raise ValueError(f"File does not match expected format for profile '{profile.name}'")

    # 2. Size limit check
    if len(data) > profile.max_size_bytes:
        raise ValueError(
            f"File size {len(data)} bytes exceeds limit of {profile.max_size_bytes} bytes"
        )

    # 3. SHA-256 dedup — check if same file (within same profile scope) was already uploaded
    file_sha256 = sha256_of_bytes(data)
    existing = await session.execute(
        select(UploadRecord).where(
            UploadRecord.sha256 == file_sha256,
            UploadRecord.profile == profile.name,
            UploadRecord.school_id == school_id,
            not_deleted(UploadRecord),
        )
    )
    existing_record = existing.scalar_one_or_none()
    if existing_record:
        logger.info("upload_deduplicated", sha256=file_sha256, upload_id=existing_record.id)
        return UploadInitiated(
            upload_id=existing_record.id,
            status=UploadStatus.DUPLICATE,
            status_url=f"/api/v1/uploads/{existing_record.id}",
            message="Duplicate file — returning existing upload",
        )

    # 4. Upload to MinIO
    upload_id = str(uuid.uuid4())
    minio_key = _build_minio_key(profile, filename, upload_id, school_id)
    upload_bytes(profile.bucket, minio_key, data)

    # 5. Record in DB
    record = UploadRecord(
        id=upload_id,
        profile=profile.name,
        filename=filename,
        size_bytes=len(data),
        sha256=file_sha256,
        minio_key=minio_key,
        bucket=profile.bucket,
        school_id=school_id,
        uploaded_by=uploaded_by,
        status=UploadStatus.READY,
    )
    session.add(record)
    await session.commit()

    logger.info("upload_complete", upload_id=upload_id, profile=profile.name, size=len(data))
    return UploadInitiated(
        upload_id=upload_id,
        status=UploadStatus.READY,
        status_url=f"/api/v1/uploads/{upload_id}",
    )
