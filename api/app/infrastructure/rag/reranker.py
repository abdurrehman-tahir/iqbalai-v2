"""bge-reranker-v2-m3 reranker via Infinity server."""
from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


async def rerank(query: str, documents: list[str], top_k: int = 5) -> list[int]:
    """Rerank documents against a query, returning the top_k indices (sorted by relevance).

    Standard RAG pattern (ARCH §7): top-50 retrieval → rerank → top-5.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.INFINITY_URL}/rerank",
            json={"query": query, "documents": documents, "model": _RERANKER_MODEL},
        )
        response.raise_for_status()
        data = response.json()
        # Sort by relevance score descending, return top_k indices
        results = sorted(data["results"], key=lambda x: x["relevance_score"], reverse=True)
        indices: list[int] = [r["index"] for r in results[:top_k]]
        logger.debug("reranked_documents", input_count=len(documents), top_k=top_k, model=_RERANKER_MODEL)
        return indices
