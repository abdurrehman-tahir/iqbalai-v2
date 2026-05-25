"""API v1 router — mounts all feature routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.files.router import router as uploads_router
from app.features.health.router import router as health_router
from app.features.smoketest.router import router as smoketest_router
from app.features.tos.router import router as tos_router
from app.features.users.router import router as users_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(smoketest_router, tags=["smoketest"])
router.include_router(uploads_router, tags=["uploads"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(tos_router)
