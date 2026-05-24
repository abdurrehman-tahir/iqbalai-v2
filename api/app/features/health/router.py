"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe — always returns 200 if the app is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe — checks that the app can accept traffic."""
    # TODO T-007+: add DB connectivity check
    return {"status": "ready"}
