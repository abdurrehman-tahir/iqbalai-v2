"""Re-export the Celery app for use by worker entrypoint."""

from app.infrastructure.celery.celery_app import celery_app

__all__ = ["celery_app"]
