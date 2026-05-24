"""Celery beat schedule — ALL scheduled jobs defined here.

Populated per feature as milestones land. Empty at M-00.
Per ARCH §10.6.
"""

from __future__ import annotations

# Beat schedule is registered in celery_app.conf.beat_schedule in celery_app.py
# Add entries here and import them in configure_celery() as features are added.
BEAT_SCHEDULE: dict[str, object] = {
    # Example format (do not uncomment — real tasks added per milestone):
    # "nightly-predictions": {
    #     "task": "app.tasks.ml_tasks.recalculate_predictions_nightly",
    #     "schedule": crontab(hour=2, minute=0),
    # },
}
