"""File upload endpoints per ARCH §11.16."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.base import not_deleted
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile, list_profiles
from app.features.files.schemas import UploadInitiated, UploadStatusResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/uploads")


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadInitiated,
    operation_id="upload_file",
)
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


@router.get(
    "/{upload_id}",
    response_model=UploadStatusResponse,
    operation_id="get_upload_status",
)
async def get_upload_status(
    upload_id: str,
    session: AsyncSession = Depends(get_db),
) -> UploadStatusResponse:
    """Get the status of a previously initiated upload."""
    result = await session.execute(
        select(UploadRecord).where(
            UploadRecord.id == upload_id,
            not_deleted(UploadRecord),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    # from_attributes maps record.id → upload_id via the schema's validation alias.
    return UploadStatusResponse.model_validate(record)
