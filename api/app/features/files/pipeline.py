"""Single parametrized upload pipeline per ARCH §11.2."""

from __future__ import annotations

import io
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

_WEBP_MAGIC_SENTINEL = b"WEBP"


def _build_minio_key(
    profile: UploadProfile, filename: str, upload_id: str, school_id: str | None
) -> str:
    """Build the MinIO object key per ARCH §11.4 strategy.

    Format: {key_prefix}/{school_id or 'global'}/{date}/{upload_id}/{filename}
    """
    date_part = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    scope = school_id or "global"
    return f"{profile.key_prefix}/{scope}/{date_part}/{upload_id}/{filename}"


def _is_webp(data: bytes) -> bool:
    """WEBP is a RIFF container — validate both the RIFF header and WEBP form type."""
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _validate_magic_bytes(data: bytes, profile: UploadProfile) -> bool:
    """Check that the file starts with one of the expected magic byte sequences."""
    if not profile.magic_bytes:
        return True
    for magic in profile.magic_bytes:
        if magic == _WEBP_MAGIC_SENTINEL:
            if _is_webp(data):
                return True
            continue
        if data[: len(magic)] == magic:
            return True
    return False


def _detect_image_format(data: bytes) -> str | None:
    """Return a Pillow-compatible format name for accepted student-question images."""
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if _is_webp(data):
        return "WEBP"
    return None


def strip_exif_metadata(data: bytes) -> bytes:
    """Re-encode an image without EXIF/metadata (ARCH §11.19 / §8.22).

    Uses Pillow (already a transitive dep via pdfplumber). Returns the original
    bytes unchanged if the payload is not a recognised image or re-encode fails
    — callers that already passed magic-byte validation should treat failure as
    a hard error via the dedicated pipeline path.
    """
    fmt = _detect_image_format(data)
    if fmt is None:
        return data
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover — pdfplumber pulls Pillow in
        raise RuntimeError("Pillow is required to strip EXIF from student images") from exc

    with Image.open(io.BytesIO(data)) as img:
        # Flatten to a clean pixel buffer so EXIF / ICC / XMP do not survive.
        cleaned = Image.new(img.mode, img.size)
        cleaned.putdata(list(img.getdata()))
        out = io.BytesIO()
        save_kwargs: dict[str, object] = {"format": fmt}
        if fmt == "JPEG":
            if cleaned.mode not in ("RGB", "L"):
                cleaned = cleaned.convert("RGB")
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
            save_kwargs["exif"] = b""
        cleaned.save(out, **save_kwargs)
        return out.getvalue()


async def list_expired_uploads(
    session: AsyncSession, *, profile_name: str, cutoff: datetime
) -> list[UploadRecord]:
    """Uploads under ``profile_name`` created before ``cutoff`` (retention sweep).

    T-170: used by ``student_questions.tasks.purge_expired_question_images``
    (and any future profile with a retention purge) to find rows past their
    ``UploadProfile.retention_days`` window that haven't been purged yet.
    """
    result = await session.execute(
        select(UploadRecord).where(
            UploadRecord.profile == profile_name,
            UploadRecord.created_at < cutoff,
            not_deleted(UploadRecord),
        )
    )
    return list(result.scalars().all())


async def purge_expired_upload(session: AsyncSession, record: UploadRecord) -> None:
    """Delete the MinIO object and soft-delete the ``upload_records`` row (T-170)."""
    from app.infrastructure.storage.client import delete_object

    delete_object(record.bucket, record.minio_key)
    record.deleted_at = datetime.now(timezone.utc)
    await session.commit()


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

    Steps: validate magic bytes → check size → optional EXIF strip → dedup
    (SHA-256) → upload to MinIO → record in DB.
    Returns UploadInitiated immediately (202 Accepted pattern).
    """
    # 1. Magic-byte validation
    if not skip_magic_check and not _validate_magic_bytes(data, profile):
        raise ValueError(f"File does not match expected format for profile '{profile.name}'")

    # 2. Size limit check (pre-strip — oversized inputs are rejected before work)
    if len(data) > profile.max_size_bytes:
        raise ValueError(
            f"File size {len(data)} bytes exceeds limit of {profile.max_size_bytes} bytes"
        )

    # 3. EXIF strip for vision-consumed profiles (T-166 / ARCH §11.19)
    if profile.strip_exif:
        try:
            data = strip_exif_metadata(data)
        except Exception as exc:
            logger.warning("exif_strip_failed", profile=profile.name, error=str(exc))
            raise ValueError("Could not process image metadata; upload rejected") from exc
        if len(data) > profile.max_size_bytes:
            raise ValueError(
                f"File size {len(data)} bytes exceeds limit of {profile.max_size_bytes} bytes"
            )

    # 4. SHA-256 dedup — check if same file (within same profile scope) was already uploaded
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

    # 5. Upload to MinIO
    upload_id = str(uuid.uuid4())
    minio_key = _build_minio_key(profile, filename, upload_id, school_id)
    upload_bytes(profile.bucket, minio_key, data)

    # 6. Record in DB
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

    logger.info(
        "upload_complete",
        upload_id=upload_id,
        profile=profile.name,
        size=len(data),
        retention_days=profile.retention_days,
        strip_exif=profile.strip_exif,
    )
    return UploadInitiated(
        upload_id=upload_id,
        status=UploadStatus.READY,
        status_url=f"/api/v1/uploads/{upload_id}",
    )
