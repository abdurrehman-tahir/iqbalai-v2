"""Admin comparative teacher metrics API schemas — T-139 (Flow 5 §3.11 #38)."""

from __future__ import annotations

from pydantic import BaseModel


class TeacherMetricsRead(BaseModel):
    """One (teacher, subject, grade) aggregate row — averaged across every
    scored lecture version in scope. Unlike the teacher-facing benchmark
    (#37), this is not anonymized: admins see real names/schools."""

    teacher_user_id: str
    teacher_name: str
    school_id: str
    school_name: str
    subject_id: str
    subject_name: str
    grade_range: str
    lecture_count: int
    avg_originality: float
    avg_depth: float
    avg_cultural_relevance: float
    avg_engagement: float
    avg_alignment: float
    avg_voice_quality: float | None
    avg_ai_learning: float
    avg_total: float
    avg_topic_relevance_pct: float | None
