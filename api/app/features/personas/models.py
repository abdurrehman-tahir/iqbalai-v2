"""ORM model for Teaching Personas — T-021."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class TeachingPersona(AuditMixin, Base):
    """Named AI teaching persona with multilingual system prompts.

    Four built-in personas ship at launch (Socratic, Nurturing, Challenger, Explainer)
    plus one Custom slot per school. Prompts are mutable by Platform Admin; changes
    apply to NEW sessions only — existing cached sessions retain the old prompt.
    """

    __tablename__ = "teaching_personas"
    # Exactly one custom-slot persona may exist (the school-customisable slot). A
    # partial unique index lets the four built-ins coexist (is_custom=False) while
    # constraining is_custom=True rows to a single occupant (ARCH §4.7).
    __table_args__ = (
        Index(
            "teaching_personas_custom_slot_uq",
            "is_custom",
            unique=True,
            postgresql_where=text("is_custom"),
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # URL-safe slug used to reference a persona in session config
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # is_custom=True means this is the school-customisable slot
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # System prompts per supported language; at minimum English is required
    system_prompt_en: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt_ur: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_sd: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_ps: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
