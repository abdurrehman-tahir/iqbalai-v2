"""Celery infrastructure module."""

from app.infrastructure.celery.celery_app import celery_app

__all__ = ["celery_app"]
