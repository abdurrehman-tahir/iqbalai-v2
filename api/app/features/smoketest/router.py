"""Smoke test endpoints — internal only, not user-facing.

These endpoints exist purely for M-00 acceptance testing.
They will be removed or gated behind platform_admin in M-01.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/smoketest")


@router.post("/rag")
async def smoketest_rag(body: dict[str, str]) -> dict[str, object]:
    """Run a sample RAG query. Returns empty chunks since no content is ingested yet."""
    query = body.get("query", "sample")
    # Import inline to avoid circular imports during app init
    from app.infrastructure.rag.retriever import retrieve
    try:
        # Try to retrieve — will return [] if collection doesn't exist yet
        chunks = await retrieve(query, collection_name="curriculum")
    except Exception:
        chunks = []
    return {"chunks": chunks, "status": "ok", "query": query}


@router.post("/llm")
async def smoketest_llm(body: dict[str, str]) -> dict[str, object]:
    """Run a sample LLM call."""
    prompt = body.get("prompt", "Say hello in one sentence.")
    from app.infrastructure.llm.client import chat
    try:
        response = await chat(
            messages=[{"role": "user", "content": prompt}],
            task="smoke_test",
            max_tokens=50,
        )
        return {"response": response, "status": "ok"}
    except Exception as exc:
        return {"response": None, "status": "error", "error": str(exc)}
