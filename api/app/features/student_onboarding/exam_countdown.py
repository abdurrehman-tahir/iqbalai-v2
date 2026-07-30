"""Shared exam-date countdown helpers — T-083 / T-107 (Flow 4 §3.7)."""

from __future__ import annotations

from datetime import date, timedelta

EXAM_DATE_MAX_YEARS = 5
EXAM_COUNTDOWN_DAYS = (30, 14, 7, 1)
EXAM_PASSED_MARKER = "passed"
FUTURE_DATE_WARNING = (
    "Exam date is more than 5 years away — you can update it anytime before your exam"
)


def future_date_warning(exam_date: date) -> str | None:
    if exam_date > date.today() + timedelta(days=365 * EXAM_DATE_MAX_YEARS):
        return FUTURE_DATE_WARNING
    return None


def parse_countdown_sent(raw: str | None) -> set[int]:
    if not raw:
        return set()
    sent: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            sent.add(int(part))
    return sent


def format_countdown_sent(sent: set[int], *, passed: bool = False) -> str | None:
    parts = [str(day) for day in sorted(sent)]
    if passed:
        parts.append(EXAM_PASSED_MARKER)
    if not parts:
        return None
    return ",".join(parts)


def has_exam_passed_notified(raw: str | None) -> bool:
    if not raw:
        return False
    return EXAM_PASSED_MARKER in {part.strip() for part in raw.split(",") if part.strip()}


def mark_exam_passed_notified(raw: str | None) -> str:
    sent = parse_countdown_sent(raw)
    return format_countdown_sent(sent, passed=True) or EXAM_PASSED_MARKER
