"""Celery application configuration.

Per ARCH §10: four queues (default, ingestion, ml, notifications),
tenant_task decorator, Redis broker.
"""

from __future__ import annotations

import structlog
from celery import Celery
from celery.signals import task_failure, task_success

logger = structlog.get_logger(__name__)

# Celery app — broker is Redis, backend is Redis
celery_app = Celery("iqbalai")


def configure_celery(broker_url: str, result_backend: str) -> None:
    """Configure Celery with broker/backend URLs. Called from app startup."""
    celery_app.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Four queues per ARCH §10.2
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
            "ml": {"exchange": "ml", "routing_key": "ml"},
            "notifications": {"exchange": "notifications", "routing_key": "notifications"},
        },
        task_default_queue="default",
        # Retry config per ARCH §10.9
        task_max_retries=3,
        task_default_retry_delay=60,
        # Beat schedule (populated per feature)
        beat_schedule={},
    )
    # shared_task / apply_async from the API process must use this broker, not amqp://localhost.
    celery_app.set_default()
    # app.features.* imports optional ingestion deps; register via tasks/celery_app.py
    celery_app.autodiscover_tasks(["app.tasks"], related_name="tasks", force=True)


def _result_backend_url(redis_url: str) -> str:
    """Celery results on Redis DB 1; broker uses REDIS_URL (typically DB 0)."""
    base, sep, db = redis_url.rpartition("/")
    if sep and db.isdigit():
        return f"{base}/1"
    return f"{redis_url.rstrip('/')}/1"


def _bootstrap_celery() -> None:
    from app.config import get_settings

    settings = get_settings()
    configure_celery(settings.REDIS_URL, _result_backend_url(settings.REDIS_URL))


_bootstrap_celery()


@task_failure.connect  # type: ignore[misc]
def on_task_failure(
    task_id: str,
    exception: Exception,
    traceback: object,
    sender: object,
    **kwargs: object,
) -> None:
    """Log task failures as structured events."""
    logger.error(
        "celery_task_failed",
        task_id=task_id,
        task_name=getattr(sender, "name", "unknown"),
        error=str(exception),
    )


@task_success.connect  # type: ignore[misc]
def on_task_success(
    result: object,
    sender: object,
    **kwargs: object,
) -> None:
    """Log task successes."""
    logger.info(
        "celery_task_succeeded",
        task_name=getattr(sender, "name", "unknown"),
    )
