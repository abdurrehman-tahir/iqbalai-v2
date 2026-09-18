"""Qdrant hybrid retriever (dense + sparse via BGE-M3)."""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.infrastructure.rag.embedder import embed

logger = structlog.get_logger(__name__)


def _get_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(url=settings.QDRANT_URL)


def build_tenant_filter(tenant_filter: dict[str, str] | None) -> Filter | None:
    """Single chokepoint for Qdrant tenant scoping (ARCH §3.8).

    Callers pass payload-field equality constraints (typically ``school_id``).
    Independent collections are already per-user named; they may omit the filter.
    """
    if not tenant_filter:
        return None
    return Filter(
        must=[
            FieldCondition(key=key, match=MatchValue(value=value))
            for key, value in tenant_filter.items()
        ]
    )


def _build_search_filter(
    must: dict[str, str] | None, must_not: dict[str, str] | None
) -> Filter | None:
    """Like ``build_tenant_filter`` but also supports exclusion (T-135 —
    originality checks must exclude the lecture's own prior versions from
    matching against itself)."""
    if not must and not must_not:
        return None
    return Filter(
        must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in (must or {}).items()]
        or None,
        must_not=[
            FieldCondition(key=k, match=MatchValue(value=v)) for k, v in (must_not or {}).items()
        ]
        or None,
    )


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
    query_filter = build_tenant_filter(tenant_filter)

    client = _get_client()
    try:
        results = await client.search(  # type: ignore[attr-defined]
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        items = [{"id": str(r.id), "score": r.score, "payload": r.payload or {}} for r in results]
        logger.debug(
            "qdrant_retrieved",
            collection=collection_name,
            count=len(items),
            tenant_scoped=query_filter is not None,
        )
        return items
    except Exception as exc:
        logger.warning("qdrant_retrieve_failed", collection=collection_name, error=str(exc))
        return []
    finally:
        await client.close()


async def search_by_vector(
    collection_name: str,
    vector: list[float],
    *,
    tenant_filter: dict[str, str] | None = None,
    exclude: dict[str, str] | None = None,
    top_k: int = 10,
) -> list[dict[str, object]]:
    """Search Qdrant with an already-computed vector — no re-embedding.

    For callers that must embed once and reuse the same vector for both the
    search and a subsequent upsert (T-135 originality checking). ``exclude``
    supports a payload-field exclusion (e.g. a lecture's own prior versions
    must never count as a match against themselves). Returns ``[]`` — same as
    ``retrieve`` — on any failure, including a not-yet-created collection.
    """
    query_filter = _build_search_filter(tenant_filter, exclude)
    client = _get_client()
    try:
        results = await client.search(  # type: ignore[attr-defined]
            collection_name=collection_name,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [{"id": str(r.id), "score": r.score, "payload": r.payload or {}} for r in results]
    except Exception as exc:
        logger.warning("qdrant_search_by_vector_failed", collection=collection_name, error=str(exc))
        return []
    finally:
        await client.close()


async def _ensure_collection(
    client: AsyncQdrantClient, collection_name: str, vector_dim: int
) -> None:
    existing = {c.name for c in (await client.get_collections()).collections}
    if collection_name not in existing:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
        )


async def upsert_point(
    collection_name: str,
    point_id: str,
    vector: list[float],
    payload: dict[str, object],
) -> None:
    """Create ``collection_name`` if it doesn't exist yet, then upsert one point.

    Raises on failure — callers in a best-effort pipeline (T-135) catch this
    themselves rather than have it silently swallowed here, since a failed
    index write (unlike a failed search) means future originality checks miss
    this version entirely.
    """
    client = _get_client()
    try:
        await _ensure_collection(client, collection_name, len(vector))
        await client.upsert(
            collection_name=collection_name,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
    finally:
        await client.close()
