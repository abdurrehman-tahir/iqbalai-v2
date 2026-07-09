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
    SchoolLibraryListResponse,
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
    "/",
    response_model=SuccessEnvelope[SchoolLibraryListResponse],
    operation_id="school_library_list_items",
    summary="List school library items visible to the caller",
    description=(
        "Returns school-public items plus the caller's own private items and selections. "
        "Supports combinable filters by subject, grade context (shows this grade and lower), "
        "language, content type, and title search."
    ),
    dependencies=[require_role("teacher")],
)
async def list_school_library_items(
    subject_id: str | None = Query(default=None, max_length=36),
    grade_level_ordinal: int | None = Query(default=None, ge=1, le=16),
    language: str | None = Query(default=None, pattern="^(en|ur|sd|ps)$"),
    content_type: str | None = Query(default=None, pattern="^(curriculum|reference)$"),
    title: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryListResponse]:
    svc = SchoolLibraryService(db)
    result = await svc.list_items(
        authentik_id=str(claims.get("sub", "")),
        subject_id=subject_id,
        grade_level_ordinal=grade_level_ordinal,
        language=language,
        content_type=content_type,
        title=title,
        limit=limit,
        offset=offset,
    )
    return success(result.model_dump(mode="json"))


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
    grade_level_ordinal: int | None = Query(default=None, ge=1, le=16),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.get_item(
        item_id,
        authentik_id=str(claims.get("sub", "")),
        grade_level_ordinal=grade_level_ordinal,
    )
    return success(SchoolLibraryItemRead.model_validate(item))


@router.delete(
    "/{item_id}",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_delete_item",
    summary="Soft-delete a school library item",
    description=(
        "Marks the item deleted. Storage and Qdrant embeddings are retained "
        "so existing lecture citations remain valid."
    ),
    dependencies=[require_role("teacher")],
)
async def delete_school_library_item(
    item_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.soft_delete_item(item_id, authentik_id=str(claims.get("sub", "")))
    logger.info("school_library_delete_endpoint", item_id=item.id)
    return success(SchoolLibraryItemRead.model_validate(item))


@router.post(
    "/{item_id}/publish",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_publish_reference",
    summary="Publish a private reference book to the school library",
    description=(
        "One-way private → school_public for reference books. "
        "Curricula are always public; public items cannot be made private."
    ),
    dependencies=[require_role("teacher")],
)
async def publish_school_library_reference(
    item_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.publish_reference(item_id, authentik_id=str(claims.get("sub", "")))
    logger.info("school_library_publish_endpoint", item_id=item.id)
    return success(SchoolLibraryItemRead.model_validate(item))


@router.patch(
    "/{item_id}/visibility",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_set_reference_visibility",
    summary="Update reference book visibility",
    description=(
        "Allows private → school_public. Blocks school_public → private with 412 "
        "PRECONDITION_FAILED."
    ),
    dependencies=[require_role("teacher")],
)
async def set_school_library_reference_visibility(
    item_id: str,
    visibility: str = Query(..., pattern="^(private|school_public)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.set_reference_visibility(
        item_id,
        visibility=visibility,
        authentik_id=str(claims.get("sub", "")),
    )
    return success(SchoolLibraryItemRead.model_validate(item))


@router.delete(
    "/{item_id}/selection",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_remove_selection",
    summary="Remove your selection of a library item",
    description=("Removes the caller's selection record. Public items remain available to others."),
    dependencies=[require_role("teacher")],
)
async def remove_school_library_selection(
    item_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.remove_selection(item_id, authentik_id=str(claims.get("sub", "")))
    logger.info("school_library_remove_selection_endpoint", item_id=item.id)
    return success(SchoolLibraryItemRead.model_validate(item))


@router.post(
    "/{item_id}/retry-ingestion",
    response_model=SuccessEnvelope[SchoolLibraryItemRead],
    operation_id="school_library_retry_ingestion",
    summary="Retry ingestion for a library item",
    description=(
        "Re-queues ingestion for items in pending or failed status. "
        "Clears the stored failure reason before retrying."
    ),
    dependencies=[require_role("teacher")],
)
async def retry_school_library_ingestion(
    item_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[SchoolLibraryItemRead]:
    svc = SchoolLibraryService(db)
    item = await svc.retry_ingestion(item_id, authentik_id=str(claims.get("sub", "")))
    logger.info("school_library_retry_ingestion_endpoint", item_id=item.id)
    return success(SchoolLibraryItemRead.model_validate(item))
