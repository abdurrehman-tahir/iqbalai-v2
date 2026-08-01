"""WebSocket router — mounts all `/ws/v1/<endpoint>` routes (ARCH §5.12).

Separate from `v1/router.py` (which is `/api/v1/...`): the locked WS URL
pattern lives outside the REST prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.features.lectures.ws_router import router as lecture_generation_ws_router

router = APIRouter()

router.include_router(lecture_generation_ws_router)
