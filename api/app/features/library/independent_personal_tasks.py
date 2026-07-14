"""Celery ingestion for independent private pool — T-074."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.celery_async import run_db
from app.features.library.independent_personal_models import (
    IndependentPersonalContent,
    PersonalContentStatus,
)
from app.infrastructure.celery.celery_app import celery_app
from app.infrastructure.ingestion.chunker import chunk_text
from app.infrastructure.ingestion.extractor import extract_text_from_pdf
from app.infrastructure.rag.embedder import embed_sync, embedding_vector_dim
from app.infrastructure.storage.client import download_bytes

logger = structlog.get_logger(__name__)

_PDF_BUCKET = "pdfs"
_EMBED_BATCH = 32
_QDRANT_NAMESPACE = uuid.UUID("8f14e45f-ceea-467a-9fd5-6d898331e9b1")


def _point_id(content_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_QDRANT_NAMESPACE, f"{content_id}:{chunk_index}"))


def _ensure_collection(client: QdrantClient, collection: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=embedding_vector_dim(),
                distance=Distance.COSINE,
            ),
        )


def _delete_qdrant_points(client: QdrantClient, collection: str, content_id: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        return
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="content_id",
                    match=MatchValue(value=content_id),
                )
            ]
        ),
    )


async def _load_item(
    session: AsyncSession,
    content_id: str,
    user_id: str,
) -> IndependentPersonalContent | None:
    result = await session.execute(
        select(IndependentPersonalContent).where(
            IndependentPersonalContent.id == content_id,
            IndependentPersonalContent.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _mark_status(
    session: AsyncSession,
    content_id: str,
    user_id: str,
    status: PersonalContentStatus,
    *,
    ingestion_error: str | None = None,
) -> None:
    values: dict[str, object] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
    }
    if ingestion_error is not None:
        values["ingestion_error"] = ingestion_error
    await session.execute(
        update(IndependentPersonalContent)
        .where(
            IndependentPersonalContent.id == content_id,
            IndependentPersonalContent.user_id == user_id,
        )
        .values(**values)
    )
    await session.commit()


@celery_app.task(  # type: ignore[misc]
    name="library.ingest_independent_personal_content",
    queue="ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def ingest_independent_personal_content(
    self: Any,
    content_id: str,
    user_id: str,
) -> dict[str, object]:
    """Parse, chunk, embed and index an independent user's private PDF."""
    logger.info("independent_personal_ingestion_started", content_id=content_id, user_id=user_id)
    settings = get_settings()

    item = run_db(lambda session: _load_item(session, content_id, user_id))
    if item is None:
        raise ValueError(f"Personal content not found: {content_id}")

    if item.status == PersonalContentStatus.AVAILABLE:
        return {"content_id": content_id, "status": "available", "skipped": True}

    run_db(
        lambda session: _mark_status(
            session,
            content_id,
            user_id,
            PersonalContentStatus.INGESTING,
        )
    )

    collection = item.vector_collection

    try:
        pdf_bytes = download_bytes(_PDF_BUCKET, item.file_key)
        pages = extract_text_from_pdf(pdf_bytes)

        all_chunks: list[tuple[str, int]] = []
        for page_info in pages:
            page_num = int(str(page_info["page"]))
            for chunk in chunk_text(str(page_info["text"]), source_type="reference"):
                all_chunks.append((chunk, page_num))

        if not all_chunks:
            raise ValueError("No chunks produced from PDF")

        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_chunks), _EMBED_BATCH):
            batch_texts = [text for text, _ in all_chunks[i : i + _EMBED_BATCH]]
            all_embeddings.extend(embed_sync(batch_texts))

        qdrant = QdrantClient(url=settings.QDRANT_URL)
        _ensure_collection(qdrant, collection)
        _delete_qdrant_points(qdrant, collection, content_id)

        points = [
            PointStruct(
                id=_point_id(content_id, idx),
                vector=embedding,
                payload={
                    "content_id": content_id,
                    "user_id": user_id,
                    "chunk_text": chunk_text_val,
                    "chunk_index": idx,
                    "page": page_num,
                    "content_type": item.content_type.value,
                },
            )
            for idx, ((chunk_text_val, page_num), embedding) in enumerate(
                zip(all_chunks, all_embeddings)
            )
        ]
        qdrant.upsert(collection_name=collection, points=points)

        run_db(
            lambda session: _mark_status(
                session,
                content_id,
                user_id,
                PersonalContentStatus.AVAILABLE,
            )
        )

        chunk_count = len(points)
        logger.info(
            "independent_personal_ingestion_complete",
            content_id=content_id,
            chunk_count=chunk_count,
        )
        return {
            "content_id": content_id,
            "chunk_count": chunk_count,
            "status": "available",
            "collection": collection,
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "independent_personal_ingestion_failed",
            content_id=content_id,
            error=error_msg,
        )
        run_db(
            lambda session: _mark_status(
                session,
                content_id,
                user_id,
                PersonalContentStatus.FAILED,
                ingestion_error=error_msg,
            )
        )
        raise self.retry(exc=exc)
