"""Student #72 teacher-activity privacy (T-162 / M-12; canonical owner T-220).

Preference on ``school.user_settings.teacher_activity_share`` (default share).
Flow 8 / M-17 T-220 owns #72 meaning for self-study and reuses this column —
no ``student_self_study_privacy`` table. Independent students: setting hidden.

Parent lecture-question UI is Flow 10 / M-19; M-12 ships a minimal parent
read path that filters via ``student_allows_teacher_share``.
"""

from __future__ import annotations
