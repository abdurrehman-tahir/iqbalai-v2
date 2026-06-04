"""Platform Library router — /admin/library endpoints (T-024).

Per ARCH §11.21: upload returns 202 Accepted with tracking info.
Platform Admin only.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.features.library.repository import LibraryRepository
from app.features.library.schemas import (
    LibraryBookListResponse,
    LibraryBookRead,
    LibraryBookUploadRequest,
    LibraryUploadResponse,
)
from app.features.library.service import LibraryService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/library", tags=["library"])


@router.post(
    "/",
    response_model=LibraryUploadResponse,
    status_code=202,
    summary="Upload a platform reference book",
    description=(
        "Upload a PDF to the Platform Library. "
        "Returns 202 immediately; ingestion runs asynchronously on the ingestion worker."
    ),
    dependencies=[require_role("platform_admin")],
)
async def upload_library_book(
    file: UploadFile,
    title: str = Query(..., min_length=1, max_length=500),
    content_type: str = Query(default="reference", pattern="^(curriculum|reference)$"),
    subject_tag: str | None = Query(default=None, max_length=255),
    grade_range_min: int | None = Query(default=None, ge=1, le=16),
    grade_range_max: int | None = Query(default=None, ge=1, le=16),
    language: str = Query(default="en", pattern="^(en|ur|sd|ps)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Upload a PDF reference book; queue ingestion task."""
    actor_id = str(claims["sub"])
    data = await file.read()
    meta = LibraryBookUploadRequest(
        title=title,
        content_type=content_type,
        subject_tag=subject_tag,
        grade_range_min=grade_range_min,
        grade_range_max=grade_range_max,
        language=language,
    )
    svc = LibraryService(db)
    result = await svc.upload(
        data=data,
        filename=file.filename or "upload.pdf",
        meta=meta,
        actor_id=actor_id,
    )
    logger.info("library_upload_endpoint", book_id=result.book_id, actor=actor_id)
    return JSONResponse(status_code=202, content=result.model_dump())


@router.get(
    "/",
    response_model=LibraryBookListResponse,
    summary="List platform reference books",
    description="Returns non-deleted books newest-first.",
    dependencies=[require_role("platform_admin")],
)
async def list_library_books(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> LibraryBookListResponse:
    """Paginated list of platform reference books."""
    repo = LibraryRepository(db)
    books = await repo.list_active(limit=limit, offset=offset)
    total = await repo.count_active()
    return LibraryBookListResponse(
        items=[LibraryBookRead.model_validate(b) for b in books],
        total=total,
    )


@router.delete(
    "/{book_id}",
    response_model=LibraryBookRead,
    summary="Soft-delete a platform reference book",
    description=(
        "Marks the book deleted. MinIO file and Qdrant embeddings are retained "
        "per §5.3 (soft-delete with citations preserved)."
    ),
    dependencies=[require_role("platform_admin")],
)
async def delete_library_book(
    book_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LibraryBookRead:
    """Soft-delete a book — embeddings retained."""
    actor_id = str(claims["sub"])
    svc = LibraryService(db)
    book = await svc.soft_delete(book_id=book_id, actor_id=actor_id)
    return LibraryBookRead.model_validate(book)  # type: ignore[return-value]
