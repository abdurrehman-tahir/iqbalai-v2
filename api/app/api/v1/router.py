"""API v1 router — mounts all feature routers."""
from __future__ import annotations

from fastapi import APIRouter

from app.features.health.router import router as health_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
