"""API v1 router — mounts all feature routers."""
from __future__ import annotations

from fastapi import APIRouter

from app.features.files.router import router as uploads_router
from app.features.health.router import router as health_router
from app.features.smoketest.router import router as smoketest_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(smoketest_router, tags=["smoketest"])
router.include_router(uploads_router, tags=["uploads"])
