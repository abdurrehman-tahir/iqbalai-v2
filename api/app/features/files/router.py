"""File upload endpoints per ARCH §11.16."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile, list_profiles
from app.features.files.schemas import UploadInitiated, UploadStatus, UploadStatusResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/uploads")


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=UploadInitiated)
async def upload_file(
    file: UploadFile,
    profile: str = "recovery_bundle",
    session: AsyncSession = Depends(get_db),
) -> UploadInitiated:
    """Upload a file through the pipeline.

    Returns 202 Accepted immediately with a tracking URL.
    Per ARCH §11.16 canonical endpoint shape.
    """
    try:
        upload_profile = get_profile(profile)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown profile '{profile}'. Valid profiles: {list_profiles()}",
        )

    data = await file.read()
    filename = file.filename or "upload"

    try:
        result = await run_upload_pipeline(
            data=data,
            filename=filename,
            profile=upload_profile,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return result


@router.get("/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    session: AsyncSession = Depends(get_db),
) -> UploadStatusResponse:
    """Get the status of a previously initiated upload."""
    result = await session.execute(
        select(UploadRecord).where(
            UploadRecord.id == upload_id,
            UploadRecord.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    return UploadStatusResponse(
        upload_id=record.id,
        status=UploadStatus(record.status),
        profile=record.profile,
        filename=record.filename,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
        minio_key=record.minio_key,
        created_at=record.created_at,
    )
