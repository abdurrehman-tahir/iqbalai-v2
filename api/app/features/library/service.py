"""Platform Library service — business logic (T-024).

Upload flow (per ARCH §11.21):
  1. Validate magic bytes + size  (pipeline.run_upload_pipeline)
  2. Global SHA-256 dedup          (LibraryRepository.get_by_sha256)
  3. Create PlatformReferenceBook  (status=processing)
  4. Enqueue library.ingest task   (Celery ingestion queue)
  5. Return 202 + tracking info

Ingestion flow (Celery task):
  1. Download bytes from MinIO
  2. Extract text with pdfplumber
  3. Chunk with RecursiveCharacterTextSplitter
  4. Embed with BGE-M3 via Infinity
  5. Upsert to Qdrant platform_chunks
  6. Update status=available, chunk_count=N
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.library.models import PlatformReferenceBook
from app.features.library.repository import LibraryRepository
from app.features.library.schemas import LibraryBookUploadRequest, LibraryUploadResponse
from app.infrastructure.audit.log import audit
from app.infrastructure.storage.client import sha256_of_bytes

logger = structlog.get_logger(__name__)

_PROFILE_NAME = "platform_reference_book"


class LibraryService:
    """Upload + list + soft-delete operations for Platform Library."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LibraryRepository(session)

    async def upload(
        self,
        data: bytes,
        filename: str,
        meta: LibraryBookUploadRequest,
        actor_id: str,
    ) -> LibraryUploadResponse:
        """Accept a PDF upload, dedup by SHA-256, create DB record, queue ingestion."""
        profile = get_profile(_PROFILE_NAME)
        file_sha256 = sha256_of_bytes(data)

        # Global SHA-256 dedup (ARCH §11.21 rule 8)
        existing = await self._repo.get_by_sha256(file_sha256)
        if existing is not None:
            logger.info("library_upload_deduped", sha256=file_sha256, book_id=existing.id)
            return LibraryUploadResponse(
                book_id=existing.id,
                upload_id=existing.upload_id,
                status="duplicate",
                message="Duplicate file — returning existing library entry.",
            )

        # Run file pipeline (magic bytes + size + MinIO upload + upload_record row)
        upload_result = await run_upload_pipeline(
            data=data,
            filename=filename,
            profile=profile,
            session=self._session,
            school_id=None,  # global scope
            uploaded_by=actor_id,
        )

        # Create library metadata record
        book = PlatformReferenceBook(
            upload_id=upload_result.upload_id,
            title=meta.title,
            content_type=meta.content_type,
            subject_tag=meta.subject_tag,
            grade_range_min=meta.grade_range_min,
            grade_range_max=meta.grade_range_max,
            language=meta.language,
            sha256=file_sha256,
            status="processing",
        )
        book = await self._repo.save(book)

        await audit(
            session=self._session,
            action="platform_reference_book.uploaded",
            actor_id=actor_id,
            target_type="platform_reference_book",
            target_id=book.id,
            metadata={"title": meta.title, "sha256": file_sha256},
        )

        # Enqueue ingestion task (Celery ingestion queue)
        from app.features.library.tasks import ingest_platform_book  # avoid circular import

        ingest_platform_book.apply_async(
            args=[book.id, upload_result.upload_id],
            queue="ingestion",
        )

        logger.info(
            "library_upload_accepted",
            book_id=book.id,
            upload_id=upload_result.upload_id,
            actor=actor_id,
        )
        return LibraryUploadResponse(
            book_id=book.id,
            upload_id=upload_result.upload_id,
            status="processing",
        )

    async def soft_delete(self, book_id: str, actor_id: str) -> PlatformReferenceBook:
        """Soft-delete a book — embeddings are retained in Qdrant per §5.3."""
        book = await self._repo.get_by_id(book_id)
        if book is None or book.deleted_at is not None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Library book not found")

        book.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()

        await audit(
            session=self._session,
            action="platform_reference_book.deleted",
            actor_id=actor_id,
            target_type="platform_reference_book",
            target_id=book_id,
            metadata={"title": book.title},
        )

        logger.info("library_book_soft_deleted", book_id=book_id, actor=actor_id)
        return book
