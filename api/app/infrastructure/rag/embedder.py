"""BGE-M3 embedder via Infinity server."""

from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_MODEL = "BAAI/bge-m3"


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using BGE-M3 via the Infinity server.

    Returns a list of dense embedding vectors (one per input text).
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.INFINITY_URL}/embeddings",
            json={"input": texts, "model": _MODEL},
        )
        response.raise_for_status()
        data = response.json()
        embeddings: list[list[float]] = [item["embedding"] for item in data["data"]]
        logger.debug("embedded_texts", count=len(texts), model=_MODEL)
        return embeddings
