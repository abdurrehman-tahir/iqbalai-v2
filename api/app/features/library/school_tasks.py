"""School Content Library ingestion — T-056 (Pattern S: parse → chunk → embed).

Queue: ingestion  (ARCH §10.2)

Pipeline:
  1. Load library item + mark ingesting
  2. Download PDF from MinIO
  3. Extract text (pdfplumber)
  4. Chunk per §7.7
  5. Embed via Infinity/BGE-M3 (or local dev embedder)
  6. Upsert vectors to school-scoped Qdrant collection + chunk rows in Postgres
  7. Mark available (or failed on terminal error)

Idempotency: natural — re-run deletes prior Qdrant points + Postgres chunk rows
for the item, then re-indexes with deterministic point IDs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.celery_async import run_db
from app.db.tenant_context import apply_school_rls
from app.features.library.curriculum_topic_extract import extract_curriculum_topic_tree_sync
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    SchoolLibraryItem,
    SchoolLibraryItemChunk,
)
from app.infrastructure.ingestion.chunker import chunk_text
from app.infrastructure.ingestion.extractor import extract_text_from_pdf
from app.infrastructure.rag.embedder import (
    embed_sync,
    embedding_vector_dim,
    school_library_collection,
)
from app.infrastructure.storage.client import download_bytes
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

_QDRANT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_PDF_BUCKET = "pdfs"
_EMBED_BATCH = 32


def _point_id(library_item_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_QDRANT_NAMESPACE, f"{library_item_id}:{chunk_index}"))


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
        logger.info("qdrant_collection_created", collection=collection)


def _delete_qdrant_points(client: QdrantClient, collection: str, library_item_id: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        return
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="library_item_id",
                    match=MatchValue(value=library_item_id),
                )
            ]
        ),
    )


async def _load_item(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
) -> SchoolLibraryItem | None:
    await apply_school_rls(session, school_id=school_id)
    result = await session.execute(
        select(SchoolLibraryItem).where(
            SchoolLibraryItem.id == library_item_id,
            SchoolLibraryItem.school_id == school_id,
            SchoolLibraryItem.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _mark_ingesting(session: AsyncSession, library_item_id: str, school_id: str) -> bool:
    """Transition pending/failed → ingesting. Returns False if already ingesting/available."""
    await apply_school_rls(session, school_id=school_id)
    result = await session.execute(
        update(SchoolLibraryItem)
        .where(
            SchoolLibraryItem.id == library_item_id,
            SchoolLibraryItem.school_id == school_id,
            SchoolLibraryItem.ingestion_status.in_(
                [LibraryIngestionStatus.PENDING, LibraryIngestionStatus.FAILED]
            ),
        )
        .values(
            ingestion_status=LibraryIngestionStatus.INGESTING,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(SchoolLibraryItem.id)
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def _mark_status(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
    status: LibraryIngestionStatus,
    *,
    ingestion_error: str | None = None,
) -> None:
    await apply_school_rls(session, school_id=school_id)
    values: dict[str, object] = {
        "ingestion_status": status,
        "updated_at": datetime.now(timezone.utc),
        "ingestion_error": ingestion_error,
    }
    if status is LibraryIngestionStatus.AVAILABLE:
        values["ingestion_error"] = None
    elif status is LibraryIngestionStatus.INGESTING:
        values["ingestion_error"] = None
    await session.execute(
        update(SchoolLibraryItem)
        .where(
            SchoolLibraryItem.id == library_item_id,
            SchoolLibraryItem.school_id == school_id,
        )
        .values(**values)
    )
    await session.commit()


async def _clear_existing_chunks(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
) -> None:
    await apply_school_rls(session, school_id=school_id)
    await session.execute(
        delete(SchoolLibraryItemChunk).where(
            SchoolLibraryItemChunk.library_item_id == library_item_id,
            SchoolLibraryItemChunk.school_id == school_id,
        )
    )
    await session.commit()


async def _persist_topic_tree(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
    topic_tree: dict[str, object],
) -> None:
    await apply_school_rls(session, school_id=school_id)
    await session.execute(
        update(SchoolLibraryItem)
        .where(
            SchoolLibraryItem.id == library_item_id,
            SchoolLibraryItem.school_id == school_id,
        )
        .values(
            topic_tree_jsonb=topic_tree,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


def _document_text(pages: list[dict[str, object]]) -> str:
    return "\n\n".join(str(page["text"]) for page in pages if page.get("text"))


async def _persist_chunks(
    session: AsyncSession,
    *,
    library_item_id: str,
    school_id: str,
    rows: list[SchoolLibraryItemChunk],
) -> None:
    await apply_school_rls(session, school_id=school_id)
    session.add_all(rows)
    await session.commit()


async def _audit_ingestion_complete(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
) -> None:
    from app.features.audit.actions import SCHOOL_LIBRARY_ITEM_INGESTED
    from app.infrastructure.audit.log import audit

    item = await _load_item(session, library_item_id, school_id)
    if item is None:
        return
    await audit(
        session=session,
        action=SCHOOL_LIBRARY_ITEM_INGESTED,
        actor_id=None,
        actor_role="system",
        target_type="school_library_item",
        target_id=item.id,
        school_id=school_id,
        metadata={
            "title": item.title,
            "content_type": item.content_type.value,
        },
    )


async def _notify_ingestion_available(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
) -> None:
    item = await _load_item(session, library_item_id, school_id)
    if item is None:
        return
    from app.features.library.school_library_notifications import notify_library_item_available

    await notify_library_item_available(session, item)


async def _notify_ingestion_failed(
    session: AsyncSession,
    library_item_id: str,
    school_id: str,
    error: str,
) -> None:
    item = await _load_item(session, library_item_id, school_id)
    if item is None:
        return
    from app.features.library.school_library_notifications import notify_library_item_failed

    await notify_library_item_failed(session, item, error=error)


@tenant_task(
    queue="ingestion",
    name="library.ingest_school_item",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    soft_time_limit=540,
    time_limit=600,
)
def ingest_school_library_item(
    self: Any,
    library_item_id: str,
    school_id: str,
) -> dict[str, object]:
    """Parse, chunk, embed and index a school library PDF.

    Natural idempotency: prior vectors + chunk rows for this item are removed
    before re-indexing; Qdrant point IDs are deterministic per chunk index.
    """
    logger.info("school_ingestion_started", library_item_id=library_item_id, school_id=school_id)
    settings = get_settings()

    item = run_db(lambda session: _load_item(session, library_item_id, school_id))
    if item is None:
        raise ValueError(f"Library item not found: {library_item_id}")

    if item.ingestion_status == LibraryIngestionStatus.AVAILABLE:
        logger.info("school_ingestion_skip_available", library_item_id=library_item_id)
        return {"library_item_id": library_item_id, "status": "available", "skipped": True}

    started = run_db(lambda session: _mark_ingesting(session, library_item_id, school_id))
    if not started and item.ingestion_status == LibraryIngestionStatus.INGESTING:
        logger.info("school_ingestion_already_running", library_item_id=library_item_id)
        return {"library_item_id": library_item_id, "status": "ingesting", "skipped": True}

    content_type = item.content_type.value
    source_type = "curriculum" if content_type == LibraryContentType.CURRICULUM.value else "reference"
    collection = school_library_collection(content_type)

    try:
        pdf_bytes = download_bytes(_PDF_BUCKET, item.storage_key)
        pages = extract_text_from_pdf(pdf_bytes)
        topic_tree_result: dict[str, object] | None = None

        if content_type == LibraryContentType.CURRICULUM.value:
            topic_tree_result = extract_curriculum_topic_tree_sync(
                document_text=_document_text(pages),
                title=item.title,
                language=item.language,
            )
            run_db(
                lambda session: _persist_topic_tree(
                    session,
                    library_item_id,
                    school_id,
                    topic_tree_result,
                )
            )

        all_chunks: list[tuple[str, int]] = []
        for page_info in pages:
            page_num = int(str(page_info["page"]))
            for chunk in chunk_text(str(page_info["text"]), source_type=source_type):
                all_chunks.append((chunk, page_num))

        if not all_chunks:
            raise ValueError("No chunks produced from PDF")

        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_chunks), _EMBED_BATCH):
            batch_texts = [text for text, _ in all_chunks[i : i + _EMBED_BATCH]]
            all_embeddings.extend(embed_sync(batch_texts))

        qdrant = QdrantClient(url=settings.QDRANT_URL)
        _ensure_collection(qdrant, collection)
        _delete_qdrant_points(qdrant, collection, library_item_id)
        run_db(lambda session: _clear_existing_chunks(session, library_item_id, school_id))

        points: list[PointStruct] = []
        chunk_rows: list[SchoolLibraryItemChunk] = []
        for idx, ((chunk_text_val, page_num), embedding) in enumerate(
            zip(all_chunks, all_embeddings)
        ):
            point_id = _point_id(library_item_id, idx)
            payload: dict[str, object] = {
                "school_id": school_id,
                "library_item_id": library_item_id,
                "chunk_text": chunk_text_val,
                "chunk_index": idx,
                "page": page_num,
                "language": item.language,
                "content_type": content_type,
            }
            if content_type == LibraryContentType.REFERENCE.value:
                payload["book_id"] = library_item_id
            else:
                payload["curriculum_id"] = library_item_id

            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))
            chunk_rows.append(
                SchoolLibraryItemChunk(
                    library_item_id=library_item_id,
                    school_id=school_id,
                    chunk_index=idx,
                    page_number=page_num,
                    qdrant_point_id=point_id,
                    chunk_text=chunk_text_val,
                )
            )

        qdrant.upsert(collection_name=collection, points=points)
        run_db(
            lambda session: _persist_chunks(
                session,
                library_item_id=library_item_id,
                school_id=school_id,
                rows=chunk_rows,
            )
        )
        run_db(
            lambda session: _mark_status(
                session,
                library_item_id,
                school_id,
                LibraryIngestionStatus.AVAILABLE,
            )
        )

        run_db(
            lambda session: _audit_ingestion_complete(session, library_item_id, school_id)
        )
        run_db(
            lambda session: _notify_ingestion_available(session, library_item_id, school_id)
        )

        chunk_count = len(points)
        logger.info(
            "school_ingestion_complete",
            library_item_id=library_item_id,
            chunk_count=chunk_count,
            collection=collection,
        )
        return {
            "library_item_id": library_item_id,
            "chunk_count": chunk_count,
            "status": "available",
            "collection": collection,
            "topic_tree_parse_degraded": (
                bool(topic_tree_result.get("parse_degraded"))
                if topic_tree_result is not None
                else None
            ),
        }

    except Exception as exc:
        error_message = str(exc)
        logger.error(
            "school_ingestion_failed",
            library_item_id=library_item_id,
            error=error_message,
        )
        retries = getattr(self.request, "retries", 0)
        max_retries = getattr(self, "max_retries", 3)
        if retries >= max_retries:
            run_db(
                lambda session: _notify_ingestion_failed(
                    session,
                    library_item_id,
                    school_id,
                    error_message,
                )
            )
            run_db(
                lambda session: _mark_status(
                    session,
                    library_item_id,
                    school_id,
                    LibraryIngestionStatus.FAILED,
                    ingestion_error=error_message,
                )
            )
            from app.infrastructure.celery.dlq import push_task_dlq

            push_task_dlq(
                "library.ingest_school_item",
                {"library_item_id": library_item_id, "school_id": school_id},
                error_message,
            )
        raise self.retry(exc=exc)
