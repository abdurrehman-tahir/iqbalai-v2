"""ORM models for Exam Syllabi and Syllabus Topics — T-020."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class ExamSyllabus(AuditMixin, SoftDeleteMixin, Base):
    """Exam syllabus catalogue entry — platform-wide, managed by Platform Admin.

    Each syllabus represents a board/curriculum (e.g. AKU-EB Grade 9-10 Urdu).
    Versioned: every update bumps version_number; old version is soft-replaced.
    """

    __tablename__ = "exam_syllabi"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_board: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade_range_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_range_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # BCP-47 language tag, e.g. "en", "ur"
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SyllabusTopic(AuditMixin, SoftDeleteMixin, Base):
    """Hierarchical topic within an ExamSyllabus.

    Supports up to depth=4 nesting (chapters → sections → sub-sections → items).
    parent_id=None means a root/chapter-level topic.
    """

    __tablename__ = "syllabus_topics"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    syllabus_id: Mapped[str] = mapped_column(String(36), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nesting depth: 0 = chapter, 1 = section, 2 = sub-section, 3 = topic, 4 = item
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
