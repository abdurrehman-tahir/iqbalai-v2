"""Tests for Celery configuration and smoke task per T-011 acceptance criteria."""

from __future__ import annotations

from app.infrastructure.celery.celery_app import celery_app, configure_celery
from app.tasks.smoke import ping

# ---------------------------------------------------------------------------
# Smoke task — direct call (no broker required)
# ---------------------------------------------------------------------------


def test_ping_returns_pong() -> None:
    """ping() called directly (not via .delay()) must return 'pong'."""
    assert ping() == "pong"


def test_ping_task_name() -> None:
    assert ping.name == "tasks.smoke.ping"


def test_ping_task_queue() -> None:
    assert ping.queue == "default"


# ---------------------------------------------------------------------------
# configure_celery — four queues (ARCH §10.2)
# ---------------------------------------------------------------------------


def test_configure_celery_sets_broker_url() -> None:
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    assert celery_app.conf.broker_url == "redis://localhost:6379/0"


def test_configure_celery_sets_result_backend() -> None:
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    assert celery_app.conf.result_backend == "redis://localhost:6379/1"


def test_configure_celery_creates_four_queues() -> None:
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    queues = celery_app.conf.task_queues
    assert "default" in queues
    assert "ingestion" in queues
    assert "ml" in queues
    assert "notifications" in queues


def test_configure_celery_default_queue_is_default() -> None:
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    assert celery_app.conf.task_default_queue == "default"


def test_configure_celery_uses_json_serializer() -> None:
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"


def test_configure_celery_acks_late_enabled() -> None:
    """Per ARCH §10.9: tasks must not be lost on worker crash."""
    configure_celery(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    )
    assert celery_app.conf.task_acks_late is True
