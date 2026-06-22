"""Coordinator bulk import router — T-037 / T-079."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.bulk_imports.schemas import BulkImportRead
from app.features.bulk_imports.service import BulkImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/coordinator/bulk-imports", tags=["bulk-imports"])


@router.post(
    "/",
    response_model=SuccessEnvelope[BulkImportRead],
    status_code=201,
    operation_id="create_bulk_import_dry_run",
    summary="Upload CSV/XLSX for dry-run validation",
    description=(
        "Coordinator uploads a student roster file. Rows are validated against grade scope "
        "and school structure; use commit to create invited enrollments."
    ),
    dependencies=[require_role("coordinator")],
)
async def create_bulk_import_dry_run(
    file: UploadFile,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    actor_id = str(claims["sub"])
    data = await file.read()
    svc = BulkImportService(db)
    result = await svc.dry_run(
        data=data,
        filename=file.filename or "import.csv",
        actor_authentik_id=actor_id,
    )
    logger.info("bulk_import_dry_run_endpoint", import_id=result.id, actor=actor_id)
    return success(result.model_dump(mode="json"))


@router.post(
    "/{import_id}/commit",
    response_model=SuccessEnvelope[BulkImportRead],
    operation_id="commit_bulk_import",
    summary="Commit a validated bulk import — enroll valid rows",
    dependencies=[require_role("coordinator")],
)
async def commit_bulk_import(
    import_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    actor_id = str(claims["sub"])
    svc = BulkImportService(db)
    result = await svc.commit(import_id=import_id, actor_authentik_id=actor_id, claims=claims)
    logger.info("bulk_import_commit_endpoint", import_id=result.id, actor=actor_id)
    return success(result.model_dump(mode="json"))


@router.get(
    "/{import_id}",
    response_model=SuccessEnvelope[BulkImportRead],
    operation_id="get_bulk_import",
    summary="Get bulk import dry-run or commit results",
    dependencies=[require_role("coordinator")],
)
async def get_bulk_import(
    import_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    actor_id = str(claims["sub"])
    svc = BulkImportService(db)
    result = await svc.get_job(import_id=import_id, actor_authentik_id=actor_id)
    return success(result.model_dump(mode="json"))
