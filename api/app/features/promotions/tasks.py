"""Promotion Celery tasks — T-253 execute_promotion (ARCH §6.21)."""

from __future__ import annotations

from typing import Any

import structlog

from app.db.celery_async import run_db
from app.features.promotions.service import EXECUTE_MAX_RETRIES
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

SOFT_TIME_LIMIT_SECONDS = 600  # 10 minutes — Flow 2 soft_time_limit for large grades
HARD_TIME_LIMIT_SECONDS = 660


@tenant_task(
    queue="default",
    name="promotions.execute_promotion",
    bind=True,
    max_retries=EXECUTE_MAX_RETRIES,
    default_retry_delay=30,
    soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
    time_limit=HARD_TIME_LIMIT_SECONDS,
)
def execute_promotion(
    self: Any,
    school_id: str,
    promotion_request_id: str,
) -> dict[str, object]:
    """Atomic promotion execution for one approved request."""
    from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

    logger.info(
        "promotion_execute_started",
        school_id=school_id,
        promotion_request_id=promotion_request_id,
    )
    try:
        result = run_db(
            lambda session: _run(
                session,
                school_id=school_id,
                promotion_request_id=promotion_request_id,
            )
        )
        return result
    except SoftTimeLimitExceeded:
        logger.error(
            "promotion_execute_timeout",
            school_id=school_id,
            promotion_request_id=promotion_request_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "promotion_execute_failed",
            school_id=school_id,
            promotion_request_id=promotion_request_id,
            error=str(exc),
        )
        try:
            raise self.retry(exc=exc) from exc
        except MaxRetriesExceededError:
            logger.error(
                "promotion_execute_retries_exhausted",
                school_id=school_id,
                promotion_request_id=promotion_request_id,
            )
            raise


async def _run(
    session: Any,
    *,
    school_id: str,
    promotion_request_id: str,
) -> dict[str, object]:
    from app.features.promotions.service import PromotionService

    svc = PromotionService(session)
    return await svc.execute_promotion_request(promotion_request_id, school_id=school_id)
