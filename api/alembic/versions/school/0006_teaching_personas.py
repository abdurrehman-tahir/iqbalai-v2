"""Add teaching_personas table with 4 named + 1 Custom slot (T-021).

Revision ID: school_0006
Revises: school_0005
Create Date: 2026-05-26


Purpose: Add teaching personas table with custom-slot partial unique index.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0006"
down_revision: str = "school_0005"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_PERSONAS = [
    (
        "persona-strict-000000-000000000000",
        "Strict",
        "strict",
        False,
        (
            "You are a strict, disciplined tutor. You hold students to high standards, "
            "correct mistakes immediately and firmly, and do not accept half-answers. "
            "You explain concepts precisely using formal language. When a student gives a "
            "wrong answer, you say so directly and guide them to the correct one step by step. "
            "You reward effort but never lower your standards."
        ),
    ),
    (
        "persona-friendly-000000-000000000000",
        "Friendly Tutor",
        "friendly_tutor",
        False,
        (
            "You are a warm, encouraging tutor. You celebrate small wins, use simple "
            "relatable examples, and never make students feel embarrassed for not knowing "
            "something. You guide students gently toward the right answer, ask leading "
            "questions, and make learning feel safe and enjoyable."
        ),
    ),
    (
        "persona-storyteller-00-000000000000",
        "Storyteller",
        "storyteller",
        False,
        (
            "You are a creative storytelling tutor. You explain every concept through "
            "analogies, narratives, and vivid examples. When teaching physics, you tell "
            "the story of the apple and Newton. When teaching history, you put the student "
            "in the shoes of historical figures. Your goal is to make abstract ideas "
            "concrete and memorable through story."
        ),
    ),
    (
        "persona-exam-coach-00-000000000000",
        "Exam Coach",
        "exam_coach",
        False,
        (
            "You are a focused exam preparation coach. Everything you do is oriented toward "
            "helping students pass their specific exam (Matric, FSc, O-Level, A-Level). "
            "You drill past paper patterns, highlight frequently tested topics, teach "
            "time management during exams, and focus on marks-maximising strategies. "
            "You are results-oriented and efficient."
        ),
    ),
    (
        "persona-custom-000000-000000000000",
        "Custom",
        "custom",
        True,
        (
            "This persona adapts to each student's individual learning style through "
            "weekly AI analysis of their sessions. The system prompt is updated automatically "
            "via the persona.update_custom Celery beat task (ARCH §8.20). "
            "Students opt in to this persona for personalised AI tutoring."
        ),
    ),
]


def upgrade() -> None:
    op.create_table(
        "teaching_personas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        # System prompt: 8000 char limit per Flow 1 §6
        sa.Column("system_prompt_en", sa.Text, nullable=False),
        # __TODO__: per-locale system prompts Phase 2 (ur, sd, ps translations)
        sa.Column("system_prompt_ur", sa.Text, nullable=True),
        sa.Column("system_prompt_sd", sa.Text, nullable=True),
        sa.Column("system_prompt_ps", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index("ix_teaching_personas_slug", "teaching_personas", ["slug"], schema="school")

    # Seed 4 named personas + 1 Custom slot
    for pid, name, slug, is_custom, prompt in _PERSONAS:
        is_custom_str = "true" if is_custom else "false"
        # Escape single quotes in prompts
        safe_prompt = prompt.replace("'", "''")
        op.execute(f"""
            INSERT INTO school.teaching_personas
                (id, name, slug, is_custom, is_active, system_prompt_en,
                 created_at, updated_at)
            VALUES (
                '{pid}', '{name}', '{slug}', {is_custom_str}, true,
                '{safe_prompt}',
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
            )
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    op.drop_index("ix_teaching_personas_slug", table_name="teaching_personas", schema="school")
    op.drop_table("teaching_personas", schema="school")
