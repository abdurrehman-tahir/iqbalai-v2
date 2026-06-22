"""Platform Library repository — DB queries (T-024, T-073)."""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantType
from app.db.base import not_deleted
from app.features.library.models import PlatformReferenceBook
from app.features.library.platform_read_models import PlatformReferenceBookReadonly

_BookModel = TypeVar("_BookModel", PlatformReferenceBook, PlatformReferenceBookReadonly)


def _read_model(tenant_type: TenantType) -> type[_BookModel]:
    if tenant_type == "independent":
        return PlatformReferenceBookReadonly  # type: ignore[return-value]
    return PlatformReferenceBook  # type: ignore[return-value]


class LibraryRepository:
    """All DB access for PlatformReferenceBook."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, book_id: str) -> PlatformReferenceBook | None:
        result = await self._session.execute(
            select(PlatformReferenceBook).where(PlatformReferenceBook.id == book_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_tenant(
        self,
        book_id: str,
        tenant_type: TenantType,
    ) -> PlatformReferenceBook | PlatformReferenceBookReadonly | None:
        model = _read_model(tenant_type)
        stmt = select(model).where(model.id == book_id)
        if model is PlatformReferenceBook:
            stmt = stmt.where(not_deleted(PlatformReferenceBook))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str) -> PlatformReferenceBook | None:
        """Global SHA-256 dedup check — returns any non-deleted record with this hash."""
        result = await self._session.execute(
            select(PlatformReferenceBook).where(
                PlatformReferenceBook.sha256 == sha256,
                not_deleted(PlatformReferenceBook),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PlatformReferenceBook]:
        """Return non-deleted books ordered by creation date desc."""
        result = await self._session.execute(
            select(PlatformReferenceBook)
            .where(not_deleted(PlatformReferenceBook))
            .order_by(PlatformReferenceBook.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_active_for_tenant(
        self,
        tenant_type: TenantType,
        *,
        limit: int = 50,
        offset: int = 0,
        content_type: str | None = None,
        language: str | None = None,
        subject_tag: str | None = None,
        title: str | None = None,
    ) -> list[PlatformReferenceBook | PlatformReferenceBookReadonly]:
        model = _read_model(tenant_type)
        stmt = select(model)
        if model is PlatformReferenceBook:
            stmt = stmt.where(not_deleted(PlatformReferenceBook))
        if content_type is not None:
            stmt = stmt.where(model.content_type == content_type)
        if language is not None:
            stmt = stmt.where(model.language == language)
        if subject_tag is not None:
            stmt = stmt.where(model.subject_tag == subject_tag)
        if title is not None:
            stmt = stmt.where(model.title.ilike(f"%{title}%"))
        stmt = stmt.order_by(model.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(PlatformReferenceBook)
            .where(not_deleted(PlatformReferenceBook))
        )
        return result.scalar_one()

    async def count_active_for_tenant(
        self,
        tenant_type: TenantType,
        *,
        content_type: str | None = None,
        language: str | None = None,
        subject_tag: str | None = None,
        title: str | None = None,
    ) -> int:
        model = _read_model(tenant_type)
        stmt = select(func.count()).select_from(model)
        if model is PlatformReferenceBook:
            stmt = stmt.where(not_deleted(PlatformReferenceBook))
        if content_type is not None:
            stmt = stmt.where(model.content_type == content_type)
        if language is not None:
            stmt = stmt.where(model.language == language)
        if subject_tag is not None:
            stmt = stmt.where(model.subject_tag == subject_tag)
        if title is not None:
            stmt = stmt.where(model.title.ilike(f"%{title}%"))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, book: PlatformReferenceBook) -> PlatformReferenceBook:
        self._session.add(book)
        await self._session.commit()
        await self._session.refresh(book)
        return book
