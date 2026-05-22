"""Smoke test Celery task — used in M-00 acceptance testing."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="tasks.smoke.ping", queue="default")
def ping() -> str:
    """Simple ping task to verify Celery worker is running."""
    return "pong"
