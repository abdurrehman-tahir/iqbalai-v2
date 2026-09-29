"""Locked student.lecture.* subjects (ARCH §9.3 / Flow 6 §3.8 / T-173)."""

from __future__ import annotations

STUDENT_LECTURE_PREFIX = "student.lecture."

STUDENT_LECTURE_QUESTION_ASKED = "student.lecture.question_asked"
STUDENT_LECTURE_HIGHLIGHT_CREATED = "student.lecture.highlight_created"
STUDENT_LECTURE_SESSION_OPENED = "student.lecture.session_opened"
STUDENT_LECTURE_SESSION_CLOSED = "student.lecture.session_closed"
STUDENT_LECTURE_SCROLL = "student.lecture.scroll"
STUDENT_LECTURE_PAGE_CHANGE = "student.lecture.page_change"
STUDENT_LECTURE_MODE_SWITCH = "student.lecture.mode_switch"

STUDENT_LECTURE_SUBJECTS: frozenset[str] = frozenset(
    {
        STUDENT_LECTURE_QUESTION_ASKED,
        STUDENT_LECTURE_HIGHLIGHT_CREATED,
        STUDENT_LECTURE_SESSION_OPENED,
        STUDENT_LECTURE_SESSION_CLOSED,
        STUDENT_LECTURE_SCROLL,
        STUDENT_LECTURE_PAGE_CHANGE,
        STUDENT_LECTURE_MODE_SWITCH,
    }
)

# M-12 T-156/T-163 ticket subjects → ARCH student.lecture.* aliases (T-173 bridge).
M12_TO_ARCH_ALIAS: dict[str, str] = {
    "student.question.asked": STUDENT_LECTURE_QUESTION_ASKED,
    "student.highlight.created": STUDENT_LECTURE_HIGHLIGHT_CREATED,
}

STUDENT_LECTURE_WILDCARD = "student.lecture.*"
STUDENT_EVENTS_STREAM = "student-events"
CONTENT_EVENTS_STREAM = "content-events"
SYSTEM_EVENTS_STREAM = "system-events"

ANALYTICS_CONSUMER = "m14-analytics"
SESSION_CONTEXT_CONSUMER = "m14-session-context"
LIVE_FEEDBACK_CONSUMER = "m14-live-feedback"

SYSTEM_EVENT_PIPELINE_LAG = "system.event_pipeline_lag"
