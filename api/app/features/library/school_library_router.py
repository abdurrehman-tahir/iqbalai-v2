"""School Content Library router — T-055."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.library.school_library_schemas import (
    SchoolLibraryItemRead,
    SchoolLibraryUploadRequest,
    SchoolLibraryUploadResponse,
)
from app.features.library.school_library_service import SchoolLibraryService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/school/library", tags=["school-library"])


@router.post(
    "/",
    response_model=SuccessEnvelope[SchoolLibraryUploadResponse],
    operation_id="school_library_upload",
    status_code=202,
    summary="Upload a PDF to the school content library",
    description=(
        "Accepts a PDF via the school_library_content profile (100 MB, per-school dedup). "
        "Returns 202 with the library item in ingestion_status=pending."
    ),
    dependencies=[require_role("teacher")],
)
async def upload_school_library_item(
    file: UploadFile,
    title: str = Query(..., min_length=1, max_length=500),
    content_type: str = Query(default="reference", pattern="^(curriculum|reference)$"),
    language: str = Query(default="en", pattern="^(en|ur|sd|ps)$"),
    subject_id: str | None = Query(default=None, max_length=36),
    grade_level_ordinal: int | None = Query(default=None, ge=1, le=16),
    visibility: str = Query(default="private", pattern="^(private|school_public)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    data = await file.read()
    meta = SchoolLibraryUploadRequest(
        title=title,
        content_type=content_type,
        language=language,
        subject_id=subject_id,
        grade_level_ordinal=grade_level_ordinal,
        visibility=visibility,
    )
    svc = SchoolLibraryService(db)
    result = await svc.upload(
        data=data,
        filename=file.filename or "upload.pdf",
        meta=meta,
        authentik_id=str(claims.get("sub", "")),
    )
    logger.info("school_library_upload_endpoint", item_id=result.item.id)
    return JSONResponse(status_code=202, content=success(result.model_dump(mode="json")))


@router.get(
    "/{item_id}",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_get_item",
    summary="Get a school library item",
    description=(
        "Returns library item metadata including ingestion status and topic_tree_jsonb "
        "for curricula. Respects school visibility rules."
    ),
    dependencies=[require_role("teacher")],
)
async def get_school_library_item(
    item_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.get_item(item_id, authentik_id=str(claims.get("sub", "")))
    return success(SchoolLibraryItemRead.model_validate(item))
