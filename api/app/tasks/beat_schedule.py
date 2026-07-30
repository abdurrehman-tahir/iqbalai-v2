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
    "self-study-exam-countdown-sweep": {
        "task": "self_study.exam_countdown_sweep",
        "schedule": crontab(hour=8, minute=0),  # daily sweep
    },
    "self-study-diagnostic-retake-sweep": {
        "task": "self_study.diagnostic_retake_sweep",
        "schedule": crontab(hour=8, minute=30),  # daily after exam countdown
    },
    "graduation-migrate-eligible-students": {
        "task": "graduation.migrate_eligible_students",
        "schedule": crontab(hour=4, minute=0),  # daily sweep
    },
    "graduation-migration-reminder-sweep": {
        "task": "graduation.migration_reminder_sweep",
        "schedule": crontab(hour=9, minute=0),  # daily sweep
    },
    # M-07 exam frameworks (ARCH §10.6).
    "framework-approval-sla-sweep": {
        "task": "framework.approval_sla_sweep",
        "schedule": crontab(hour=7, minute=0),  # daily: reminder@7d, escalation@14d
    },
    # Runs daily; the task re-researches PUBLISHED frameworks whose last run is older
    # than FRAMEWORK_REFRESH_DAYS (default 90) — cadence enforced in the task (T-095).
    "refresh-exam-frameworks": {
        "task": "framework.refresh_quarterly",
        "schedule": crontab(hour=22, minute=0),  # 03:00 PKT
    },
}
