"""Celery beat schedule — ALL scheduled jobs defined here.

Populated per feature as milestones land. Empty at M-00.
Per ARCH §10.6.
"""

from __future__ import annotations

from celery.schedules import crontab

# Beat schedule is registered in celery_app.conf.beat_schedule in celery_app.py
# Add entries here and import them in configure_celery() as features are added.
BEAT_SCHEDULE: dict[str, object] = {
    "account-expire-stale-invites": {
        "task": "account.expire_stale_invites",
        "schedule": crontab(minute=0),  # hourly sweep
    },
    "unlinked-parent-auto-suspend-sweep": {
        "task": "unlinked_parent.auto_suspend_sweep",
        "schedule": crontab(hour=3, minute=0),  # daily sweep
    },
}
