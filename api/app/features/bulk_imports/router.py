"""Coordinator bulk import router — T-037."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import success
from app.features.bulk_imports.schemas import BulkImportRead
from app.features.bulk_imports.service import BulkImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/coordinator/bulk-imports", tags=["bulk-imports"])


@router.post(
    "/",
    response_model=dict,
    status_code=201,
    summary="Upload CSV/XLSX for dry-run validation",
    description=(
        "Coordinator uploads a student roster file. Rows are validated against grade scope; "
        "no accounts are created until M-06."
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


@router.get(
    "/{import_id}",
    response_model=dict,
    summary="Get bulk import dry-run results",
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
