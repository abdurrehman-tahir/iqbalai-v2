"""T-216 / T-218 / T-220 unit coverage."""

from __future__ import annotations

from datetime import date

from app.features.self_study.granularity import select_granularity
from app.features.self_study.models import StudyPlanGranularity
from app.features.self_study.privacy import privacy_visible_for_tenant
from app.features.self_study.reminders import dispatch_reminder_channels
from app.features.self_study.schemas import ReminderPreferencesRead
from app.tasks.beat_schedule import BEAT_SCHEDULE


def test_granularity_bands() -> None:
    today = date(2026, 10, 15)
    assert select_granularity(exam_date=date(2026, 10, 25), today=today) == StudyPlanGranularity.DAY
    assert (
        select_granularity(exam_date=date(2026, 12, 1), today=today)
        == StudyPlanGranularity.THREE_DAY
    )
    assert select_granularity(exam_date=date(2027, 4, 1), today=today) == StudyPlanGranularity.WEEK


def test_reminder_channels_degrade_without_env(monkeypatch: object) -> None:
    class _S:
        FCM_SERVER_KEY = None
        FCM_PROJECT_ID = None
        EMAIL_API_KEY = None
        BREVO_API_KEY = None
        SMS_API_KEY = None

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "app.config.get_settings",
        lambda: _S(),
    )
    prefs = ReminderPreferencesRead(
        push_enabled=True,
        email_enabled=True,
        sms_enabled=True,
        timezone="Asia/Karachi",
    )
    out = dispatch_reminder_channels(prefs=prefs, title="t", body="b")
    assert out["push"] == "skipped_no_env"
    assert out["email"] == "skipped_no_env"
    assert out["sms"] == "skipped_no_env"


def test_reminder_respects_prefs(monkeypatch: object) -> None:
    class _S:
        FCM_SERVER_KEY = "x"
        FCM_PROJECT_ID = "y"
        EMAIL_API_KEY = "e"
        BREVO_API_KEY = None
        SMS_API_KEY = "s"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "app.config.get_settings",
        lambda: _S(),
    )
    prefs = ReminderPreferencesRead(
        push_enabled=False,
        email_enabled=True,
        sms_enabled=False,
        timezone="Asia/Karachi",
    )
    out = dispatch_reminder_channels(prefs=prefs, title="t", body="b")
    assert out["push"] == "skipped_pref"
    assert out["email"] == "sent"
    assert out["sms"] == "skipped_pref"


def test_privacy_hidden_for_independent() -> None:
    assert privacy_visible_for_tenant("school") is True
    assert privacy_visible_for_tenant("independent") is False


def test_m17_beat_entries_registered() -> None:
    assert "self-study-refine-granularity" in BEAT_SCHEDULE
    assert "self-study-send-session-reminders" in BEAT_SCHEDULE
    assert "self-study-check-adherence" in BEAT_SCHEDULE
