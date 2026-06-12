"""IqbalAI v2 — FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.core.exceptions import setup_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import AuthMiddleware
from app.infrastructure.celery.celery_app import celery_app  # noqa: F401 — Redis broker bootstrap
from app.infrastructure.events import close_nats, init_nats

# Register ingestion tasks on the Redis-backed Celery app before any apply_async call.
import app.features.library.tasks  # noqa: F401, E402

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    configure_logging()
    logger.info("iqbalai_api_starting", version=application.version)
    await init_nats()
    yield
    await close_nats()
    logger.info("iqbalai_api_stopping")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="IqbalAI API",
        version="0.1.0",
        description="IqbalAI v2 backend — AI-powered education platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Auth runs inner; CORS runs outer so OPTIONS preflight is answered before JWT checks.
    application.add_middleware(AuthMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    setup_exception_handlers(application)

    # Routers
    application.include_router(v1_router, prefix="/api/v1")

    # Prometheus metrics at /metrics
    Instrumentator().instrument(application).expose(application, endpoint="/metrics")

    return application


app = create_app()
