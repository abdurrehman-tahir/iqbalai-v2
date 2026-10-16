"""Book categorisation + prep-book gate — T-213 (Flow 8 §3.4)."""

from __future__ import annotations

from typing import Literal, cast

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.models import (
    IndependentStudentMaterial,
    MaterialBookType,
    SchoolStudentMaterial,
)
from app.features.self_study.schemas import SelfStudyMaterialRead
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

PREP_BOOK_GATE_ERROR = "Please upload a prep question book to generate a study plan."
BookTypeLiteral = Literal["prep_questions", "reference_content"]


def _to_read(
    row: SchoolStudentMaterial | IndependentStudentMaterial,
    *,
    tenant_type: Literal["school", "independent"],
) -> SelfStudyMaterialRead:
    return SelfStudyMaterialRead(
        id=row.id,
        tenant_type=tenant_type,
        title=row.title,
        source_type=cast(Literal["pdf", "camera", "gallery", "typed"], row.source_type.value),
        book_type=(cast(BookTypeLiteral, row.book_type.value) if row.book_type else None),
        added_to_library=row.added_to_library,
        storage_key=row.storage_key,
        has_ocr_text=bool(row.ocr_text),
    )


class SelfStudyCategorisationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    async def categorise(
        self,
        claims: dict[str, object],
        *,
        material_id: str,
        book_type: BookTypeLiteral,
    ) -> SelfStudyMaterialRead:
        tenant = get_tenant_type(claims)
        bt = MaterialBookType(book_type)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(IndependentStudentMaterial).where(
                    IndependentStudentMaterial.id == material_id,
                    IndependentStudentMaterial.student_user_id == ind_user.id,
                    IndependentStudentMaterial.added_to_library.is_(True),
                    not_deleted(IndependentStudentMaterial),
                )
            )
            ind_row = result.scalar_one_or_none()
            if ind_row is None:
                raise NotFoundError("Material not found in your library")
            ind_row.book_type = bt
            await self._session.commit()
            await self._session.refresh(ind_row)
            logger.info(
                "self_study_material_categorised",
                tenant="independent",
                material_id=ind_row.id,
                book_type=book_type,
            )
            return _to_read(ind_row, tenant_type="independent")

        school_user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolStudentMaterial).where(
                SchoolStudentMaterial.id == material_id,
                SchoolStudentMaterial.student_user_id == school_user.id,
                SchoolStudentMaterial.added_to_library.is_(True),
                not_deleted(SchoolStudentMaterial),
            )
        )
        school_row = result.scalar_one_or_none()
        if school_row is None:
            raise NotFoundError("Material not found in your library")
        school_row.book_type = bt
        await self._session.commit()
        await self._session.refresh(school_row)
        logger.info(
            "self_study_material_categorised",
            tenant="school",
            material_id=school_row.id,
            book_type=book_type,
        )
        return _to_read(school_row, tenant_type="school")

    async def has_prep_book(self, claims: dict[str, object]) -> bool:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(func.count())
                .select_from(IndependentStudentMaterial)
                .where(
                    IndependentStudentMaterial.student_user_id == ind_user.id,
                    IndependentStudentMaterial.added_to_library.is_(True),
                    IndependentStudentMaterial.book_type == MaterialBookType.PREP_QUESTIONS,
                    not_deleted(IndependentStudentMaterial),
                )
            )
            return int(result.scalar_one()) > 0

        school_user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(func.count())
            .select_from(SchoolStudentMaterial)
            .where(
                SchoolStudentMaterial.student_user_id == school_user.id,
                SchoolStudentMaterial.added_to_library.is_(True),
                SchoolStudentMaterial.book_type == MaterialBookType.PREP_QUESTIONS,
                not_deleted(SchoolStudentMaterial),
            )
        )
        return int(result.scalar_one()) > 0

    async def require_prep_book_or_raise(self, claims: dict[str, object]) -> None:
        if not await self.has_prep_book(claims):
            raise ValidationError(PREP_BOOK_GATE_ERROR)
