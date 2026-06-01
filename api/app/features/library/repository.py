"""Platform Library repository — DB queries (T-024)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.library.models import PlatformReferenceBook


class LibraryRepository:
    """All DB access for PlatformReferenceBook."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, book_id: str) -> PlatformReferenceBook | None:
        result = await self._session.execute(
            select(PlatformReferenceBook).where(PlatformReferenceBook.id == book_id)
        )
        return result.scalar_one_or_none()  # type: ignore[return-value]

    async def get_by_sha256(self, sha256: str) -> PlatformReferenceBook | None:
        """Global SHA-256 dedup check — returns any non-deleted record with this hash."""
        result = await self._session.execute(
            select(PlatformReferenceBook).where(
                PlatformReferenceBook.sha256 == sha256,
                PlatformReferenceBook.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()  # type: ignore[return-value]

    async def list_active(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PlatformReferenceBook]:
        """Return non-deleted books ordered by creation date desc."""
        result = await self._session.execute(
            select(PlatformReferenceBook)
            .where(PlatformReferenceBook.deleted_at.is_(None))
            .order_by(PlatformReferenceBook.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count())
            .select_from(PlatformReferenceBook)
            .where(PlatformReferenceBook.deleted_at.is_(None))
        )
        return result.scalar_one()  # type: ignore[return-value]

    async def save(self, book: PlatformReferenceBook) -> PlatformReferenceBook:
        self._session.add(book)
        await self._session.commit()
        await self._session.refresh(book)
        return book
