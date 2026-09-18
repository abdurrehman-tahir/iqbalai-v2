"""Quiz API schemas — T-145/T-146/T-147."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StudentQuizCardRead(BaseModel):
    """Dashboard card for one of the student's quizzes (T-145)."""

    assignment_id: str
    quiz_id: str
    lecture_id: str
    lecture_topic: str
    lecture_title: str
    question_count: int
    status: Literal["pending", "published", "attempted", "completed"]
    assigned_at: datetime


class QuizOptionRead(BaseModel):
    key: str
    text: str


class StudentQuizQuestionRead(BaseModel):
    id: str
    ordinal: int
    stem: str
    options: list[QuizOptionRead]
    # correct_answer intentionally omitted until after submit


class StudentQuizDetailRead(BaseModel):
    assignment_id: str
    quiz_id: str
    lecture_id: str
    lecture_topic: str
    status: str
    questions: list[StudentQuizQuestionRead]


class QuizSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class QuizQuestionResultRead(BaseModel):
    question_id: str
    ordinal: int
    stem: str
    selected: str | None
    correct_answer: str
    is_correct: bool
    source_excerpt: str | None = None


class QuizAttemptResultRead(BaseModel):
    assignment_id: str
    attempt_id: str
    score: int
    max_score: int
    status: str
    questions: list[QuizQuestionResultRead]


class QuizAggregateHotspotRead(BaseModel):
    question_ordinal: int
    difficulty: str
    incorrect_rate: float


class QuizOfferingAggregateRead(BaseModel):
    lecture_id: str
    lecture_topic: str
    assigned_count: int
    completed_count: int
    completion_rate: float
    average_score: float | None
    hotspots: list[QuizAggregateHotspotRead]


class TeacherStudentQuizResultRead(BaseModel):
    student_user_id: str
    student_display_name: str
    assignment_id: str
    status: str
    score: int | None = None
    max_score: int | None = None
    calibration: dict[str, Any] | None = None
