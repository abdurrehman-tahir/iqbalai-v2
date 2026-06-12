"""School Admin scoped endpoints — T-032."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import success
from app.features.schools.schemas import SchoolRead
from app.features.schools.service import SchoolService

router = APIRouter(prefix="/school/admin", tags=["school-admin"])


def _caller_role(claims: dict[str, object]) -> str:
    return str(claims.get("role", ""))


@router.get(
    "/school",
    response_model=dict,
    summary="Get the School Admin's own school",
    operation_id="school_admin_get_my_school",
    dependencies=[require_role("school_admin")],
)
async def get_my_school(
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SchoolService(db)
    school = await svc.get_my_school(claims, _caller_role(claims))
    return success(SchoolRead.model_validate(school).model_dump())


@router.get(
    "/schools/{school_id}",
    response_model=dict,
    summary="Get a school by ID (School Admin — own school only)",
    operation_id="school_admin_get_school",
    dependencies=[require_role("school_admin")],
)
async def get_school_by_id(
    school_id: str,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SchoolService(db)
    school = await svc.get_school(school_id, claims, _caller_role(claims))
    return success(SchoolRead.model_validate(school).model_dump())
