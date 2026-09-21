"""Student #72 teacher-activity privacy (T-162 / M-12).

Lecture-Q&A-facing preference on ``school.user_settings.teacher_activity_share``.
Default = share (Open Q12). Changes are audit-logged (§14.10).

BLOCKED-HOOK: Flow 8 / M-17 T-220 is the CANONICAL owner of #72 storage
(``student_self_study_privacy``). M-17 must reconcile to this same column — do
not create a second preference store. Independent students: #72 is hidden (N/A).

Parent lecture-question UI is Flow 10 / M-19; M-12 ships a minimal parent
read path that filters via ``student_allows_teacher_share``.
"""

from __future__ import annotations
