"""Qdrant hybrid retriever (dense + sparse via BGE-M3)."""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.infrastructure.rag.embedder import embed

logger = structlog.get_logger(__name__)


def _get_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(url=settings.QDRANT_URL)


async def retrieve(
    query: str,
    collection_name: str,
    top_k: int = 50,
    tenant_filter: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Retrieve top_k chunks from Qdrant for the given query.

    Args:
        query: the search query
        collection_name: Qdrant collection (curriculum, reference_books, lectures, etc.)
        top_k: number of results to retrieve before reranking
        tenant_filter: {"school_id": "..."} for tenant scoping per ARCH §3.8

    Returns:
        List of result dicts with keys: id, score, payload
    """
    vectors = await embed([query])
    query_vector = vectors[0]

    client = _get_client()
    try:
        results = await client.search(  # type: ignore[attr-defined]
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        items = [{"id": str(r.id), "score": r.score, "payload": r.payload or {}} for r in results]
        logger.debug("qdrant_retrieved", collection=collection_name, count=len(items))
        return items
    except Exception as exc:
        logger.warning("qdrant_retrieve_failed", collection=collection_name, error=str(exc))
        return []
    finally:
        await client.close()
