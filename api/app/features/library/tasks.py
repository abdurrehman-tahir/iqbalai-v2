"""Celery ingestion task for platform reference books (T-024).

Queue: ingestion  (per ARCH §10.2 — heavy IO, PDF parsing + embeddings)

Pipeline:
  1. Download PDF bytes from MinIO
  2. Extract text per page (pdfplumber)
  3. Chunk text (RecursiveCharacterTextSplitter — pre-approved deviation)
  4. Embed chunks (BGE-M3 via Infinity — synchronous httpx call)
  5. Upsert vectors to Qdrant ``platform_chunks`` collection
  6. Update PlatformReferenceBook status → available, chunk_count=N
  On failure → status=ingestion_failed + system notification
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import structlog
from celery import shared_task
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import get_settings
from app.infrastructure.ingestion.chunker import chunk_text
from app.infrastructure.ingestion.extractor import extract_text_from_pdf
from app.infrastructure.storage.client import download_bytes

logger = structlog.get_logger(__name__)

_COLLECTION = "platform_chunks"
_EMBEDDING_MODEL = "BAAI/bge-m3"
# BGE-M3 dense vector dimension
_VECTOR_DIM = 1024


def _embed_sync(texts: list[str]) -> list[list[float]]:
    """Call Infinity embeddings server synchronously (used inside Celery task)."""
    settings = get_settings()
    response = httpx.post(
        f"{settings.INFINITY_URL}/embeddings",
        json={"input": texts, "model": _EMBEDDING_MODEL},
        timeout=60.0,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return [item["embedding"] for item in data["data"]]


def _ensure_collection(client: QdrantClient) -> None:
    """Create Qdrant collection if it does not exist."""
    existing = {c.name for c in client.get_collections().collections}
    if _COLLECTION not in existing:
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info("qdrant_collection_created", collection=_COLLECTION)


async def _update_book_status(book_id: str, status: str, chunk_count: int | None = None) -> None:
    """Async helper — updates PlatformReferenceBook in the DB."""
    from datetime import datetime, timezone

    from sqlalchemy import update

    from app.db.session import async_session_factory
    from app.features.library.models import PlatformReferenceBook

    async with async_session_factory() as session:
        stmt = (
            update(PlatformReferenceBook)
            .where(PlatformReferenceBook.id == book_id)
            .values(
                status=status,
                chunk_count=chunk_count,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.execute(stmt)
        await session.commit()

    logger.info("book_status_updated", book_id=book_id, status=status, chunk_count=chunk_count)


async def _get_upload_minio_key(upload_id: str) -> tuple[str, str]:
    """Return (minio_key, bucket) for the given upload_id."""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.features.files.models import UploadRecord

    async with async_session_factory() as session:
        result = await session.execute(select(UploadRecord).where(UploadRecord.id == upload_id))
        record = result.scalar_one_or_none()
        if record is None:
            raise ValueError(f"UploadRecord not found: {upload_id}")
        return record.minio_key, record.bucket


async def _notify_failure(book_id: str, actor_id: str | None, error: str) -> None:
    """Send system notification for ingestion failure."""
    from app.db.session import async_session_factory
    from app.infrastructure.notifications.publish import publish_notification

    async with async_session_factory() as session:
        await publish_notification(
            session=session,
            recipient_user_id=actor_id or "platform_admin",
            feature_namespace="system",
            template_key="system.platform_library_ingest_failed",
            title="Library ingestion failed",
            body=f"Book {book_id} could not be ingested: {error[:200]}",
            metadata={"book_id": book_id, "error": error[:500]},
        )


@shared_task(  # type: ignore[misc]
    name="library.ingest_platform_book",
    queue="ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def ingest_platform_book(
    self: Any,  # Celery task instance
    book_id: str,
    upload_id: str,
) -> dict[str, object]:
    """Download, extract, chunk, embed and index a platform reference book.

    Returns a summary dict on success.
    """
    logger.info("ingestion_started", book_id=book_id, upload_id=upload_id)
    settings = get_settings()

    try:
        # 1. Fetch MinIO key
        minio_key, bucket = asyncio.run(_get_upload_minio_key(upload_id))

        # 2. Download PDF bytes
        pdf_bytes = download_bytes(bucket, minio_key)

        # 3. Extract text per page
        pages = extract_text_from_pdf(pdf_bytes)

        # 4. Chunk — flatten pages into chunks, keep page number in metadata
        all_chunks: list[tuple[str, int]] = []  # (chunk_text, page_number)
        for page_info in pages:
            page_num = int(str(page_info["page"]))  # page_info values are object; str() is safe
            chunks = chunk_text(str(page_info["text"]))
            for chunk in chunks:
                all_chunks.append((chunk, page_num))

        if not all_chunks:
            raise ValueError("No chunks produced from PDF")

        # 5. Embed in batches of 32
        batch_size = 32
        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_chunks), batch_size):
            batch_texts = [c for c, _ in all_chunks[i : i + batch_size]]
            embeddings = _embed_sync(batch_texts)
            all_embeddings.extend(embeddings)

        # 6. Upsert to Qdrant
        qdrant = QdrantClient(url=settings.QDRANT_URL)
        _ensure_collection(qdrant)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "book_id": book_id,
                    "upload_id": upload_id,
                    "chunk_text": chunk_text_val,
                    "chunk_index": idx,
                    "page": page_num,
                },
            )
            for idx, ((chunk_text_val, page_num), embedding) in enumerate(
                zip(all_chunks, all_embeddings)
            )
        ]
        qdrant.upsert(collection_name=_COLLECTION, points=points)

        chunk_count = len(points)

        # 7. Update DB status → available
        asyncio.run(_update_book_status(book_id, "available", chunk_count))

        logger.info(
            "ingestion_complete",
            book_id=book_id,
            chunk_count=chunk_count,
        )
        return {"book_id": book_id, "chunk_count": chunk_count, "status": "available"}

    except Exception as exc:
        logger.error("ingestion_failed", book_id=book_id, error=str(exc))
        # Mark book as failed in DB
        asyncio.run(_update_book_status(book_id, "ingestion_failed"))
        # Notify Platform Admin
        asyncio.run(_notify_failure(book_id, actor_id=None, error=str(exc)))
        # Retry up to max_retries
        raise self.retry(exc=exc)
