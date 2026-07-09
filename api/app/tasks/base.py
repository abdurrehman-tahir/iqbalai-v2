"""Celery task decorators — tenant_task per ARCH §10.4."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import structlog

from app.infrastructure.celery.celery_app import celery_app

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def _task_param_names(fn: Callable[..., Any]) -> list[str]:
    return [name for name in inspect.signature(fn).parameters if name != "self"]


def _extract_school_id(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """Return school_id from bound task arguments or raise."""
    params = _task_param_names(fn)
    bound = dict(zip(params, args, strict=False))
    bound.update(kwargs)
    school_id = bound.get("school_id")
    if school_id is None or str(school_id).strip() == "":
        raise TypeError(
            f"@tenant_task requires a non-empty `school_id` parameter; "
            f"task {fn.__name__!r} is missing it."
        )
    return str(school_id)


def tenant_task(**celery_kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Wrap a Celery task with tenant context validation and structured logging."""
    bind = bool(celery_kwargs.get("bind", False))

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if "school_id" not in inspect.signature(fn).parameters:
            raise TypeError(f"@tenant_task requires `school_id` in {fn.__name__!r}'s signature.")

        task_name = celery_kwargs.get("name", fn.__name__)

        if bind:

            @celery_app.task(**celery_kwargs)  # type: ignore[misc]
            @wraps(fn)
            def wrapper(self: Any, *args: Any, **kwargs: Any) -> R:
                school_id = _extract_school_id(fn, args, kwargs)
                structlog.contextvars.bind_contextvars(
                    school_id=school_id,
                    task_name=task_name,
                )
                logger.info("tenant_task_started", school_id=school_id, task_name=task_name)
                try:
                    return fn(self, *args, **kwargs)
                finally:
                    structlog.contextvars.unbind_contextvars("school_id", "task_name")

        else:

            @celery_app.task(**celery_kwargs)  # type: ignore[misc]
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> R:
                school_id = _extract_school_id(fn, args, kwargs)
                structlog.contextvars.bind_contextvars(
                    school_id=school_id,
                    task_name=task_name,
                )
                logger.info("tenant_task_started", school_id=school_id, task_name=task_name)
                try:
                    return fn(*args, **kwargs)
                finally:
                    structlog.contextvars.unbind_contextvars("school_id", "task_name")

        return wrapper  # type: ignore[return-value]

    return decorator
