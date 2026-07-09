"""Embedding via Infinity (prod) or sentence-transformers (local dev).

Production stack lock: BGE-M3 via Infinity (STACK_LOCK §4.3).
Local dev: set EMBEDDING_PROVIDER=local to embed inside the Celery worker (~400 MB RAM)
instead of the Infinity container (~2 GB).
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_INFINITY_MODEL = "BAAI/bge-m3"
_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_INFINITY_DIM = 1024
_LOCAL_DIM = 384

_local_model: Any | None = None


def embedding_provider() -> Literal["infinity", "local"]:
    provider = get_settings().EMBEDDING_PROVIDER
    if provider not in ("infinity", "local"):
        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider!r}")
    return provider  # type: ignore[return-value]


def embedding_model_name() -> str:
    settings = get_settings()
    if settings.EMBEDDING_MODEL:
        return settings.EMBEDDING_MODEL
    return _LOCAL_MODEL if settings.EMBEDDING_PROVIDER == "local" else _INFINITY_MODEL


def embedding_vector_dim() -> int:
    settings = get_settings()
    if settings.EMBEDDING_VECTOR_DIM > 0:
        return settings.EMBEDDING_VECTOR_DIM
    return _LOCAL_DIM if settings.EMBEDDING_PROVIDER == "local" else _INFINITY_DIM


def platform_chunks_collection() -> str:
    """Separate Qdrant collection per provider so vector dims never clash."""
    if embedding_provider() == "local":
        return "platform_chunks_local"
    return "platform_chunks"


def reference_book_chunks_collection() -> str:
    """School-tier reference book vectors (ARCH §7.6)."""
    if embedding_provider() == "local":
        return "reference_book_chunks_local"
    return "reference_book_chunks"


def curriculum_chunks_collection() -> str:
    """School-tier curriculum vectors (ARCH §7.6)."""
    if embedding_provider() == "local":
        return "curriculum_chunks_local"
    return "curriculum_chunks"


def school_library_collection(content_type: str) -> str:
    """Resolve Qdrant collection for a school library item content type."""
    if content_type == "curriculum":
        return curriculum_chunks_collection()
    return reference_book_chunks_collection()


def independent_personal_collection(user_id: str) -> str:
    """Per-user Qdrant namespace for independent private pool (ARCH §3.16)."""
    prefix = (
        "independent_personal_local" if embedding_provider() == "local" else "independent_personal"
    )
    return f"{prefix}_{user_id}"


def _infinity_embed_sync(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    model = embedding_model_name()
    response = httpx.post(
        f"{settings.INFINITY_URL}/embeddings",
        json={"input": texts, "model": model},
        timeout=60.0,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return [item["embedding"] for item in data["data"]]


def _get_local_model() -> Any:
    global _local_model
    if _local_model is None:
        from fastembed import TextEmbedding

        model_name = embedding_model_name()
        logger.info("local_embedder_loading", model=model_name)
        _local_model = TextEmbedding(model_name=model_name)
        logger.info("local_embedder_loaded", model=model_name)
    return _local_model


def _local_embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    return [list(vec) for vec in model.embed(texts)]


def embed_sync(texts: list[str]) -> list[list[float]]:
    """Embed texts synchronously (Celery tasks)."""
    if embedding_provider() == "local":
        embeddings = _local_embed_sync(texts)
    else:
        embeddings = _infinity_embed_sync(texts)
    logger.debug(
        "embedded_texts",
        count=len(texts),
        provider=embedding_provider(),
        model=embedding_model_name(),
    )
    return embeddings


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts (async API / retriever)."""
    if embedding_provider() == "local":
        import asyncio

        return await asyncio.to_thread(embed_sync, texts)

    settings = get_settings()
    model = embedding_model_name()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.INFINITY_URL}/embeddings",
            json={"input": texts, "model": model},
        )
        response.raise_for_status()
        data = response.json()
        embeddings: list[list[float]] = [item["embedding"] for item in data["data"]]
        logger.debug(
            "embedded_texts",
            count=len(texts),
            provider="infinity",
            model=model,
        )
        return embeddings
