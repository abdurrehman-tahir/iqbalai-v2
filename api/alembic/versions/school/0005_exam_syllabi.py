"""Add exam_syllabi and syllabus_topics tables (T-020).

Revision ID: school_0005
Revises: school_0004
Create Date: 2026-05-26


Purpose: Add exam syllabi and syllabus topics tables.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0005"
down_revision: str = "school_0004"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    # ── exam_syllabi ──────────────────────────────────────────────────────────
    # Platform-level, no school_id. Versioned: editing creates v(n+1).
    op.create_table(
        "exam_syllabi",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exam_board", sa.String(100), nullable=False),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("grade_range_min", sa.Integer, nullable=True),
        sa.Column("grade_range_max", sa.Integer, nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index("ix_exam_syllabi_name", "exam_syllabi", ["name"], schema="school")
    op.create_index("ix_exam_syllabi_is_active", "exam_syllabi", ["is_active"], schema="school")

    # ── syllabus_topics ───────────────────────────────────────────────────────
    # Hierarchical tree; depth limited to 4 at application layer.
    op.create_table(
        "syllabus_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("syllabus_id", sa.String(36), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_syllabus_topics_syllabus_id", "syllabus_topics", ["syllabus_id"], schema="school"
    )
    op.create_index(
        "ix_syllabus_topics_parent_id", "syllabus_topics", ["parent_id"], schema="school"
    )

    # ── Seed: 4 launch syllabi (per T-020 demo script) ────────────────────────
    syllabi = [
        (
            "syl-matric-punjab-000-000000000000",
            "Matric Punjab Board",
            "BISE Punjab",
            "Punjab",
            9,
            10,
        ),
        ("syl-fsc-punjab-00000-000000000000", "FSc Punjab Board", "BISE Punjab", "Punjab", 11, 12),
        (
            "syl-olevel-cambridge-000000000000",
            "O-Level Cambridge",
            "Cambridge IGCSE",
            "International",
            9,
            10,
        ),
        (
            "syl-alevel-cambridge-000000000000",
            "A-Level Cambridge",
            "Cambridge A-Level",
            "International",
            11,
            12,
        ),
    ]
    for sid, name, board, region, gmin, gmax in syllabi:
        op.execute(f"""
            INSERT INTO school.exam_syllabi
                (id, name, exam_board, region, grade_range_min, grade_range_max,
                 version_number, is_active, created_at, updated_at)
            VALUES (
                '{sid}', '{name}', '{board}', '{region}', {gmin}, {gmax},
                1, true,
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
            )
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    op.drop_index("ix_syllabus_topics_parent_id", table_name="syllabus_topics", schema="school")
    op.drop_index("ix_syllabus_topics_syllabus_id", table_name="syllabus_topics", schema="school")
    op.drop_table("syllabus_topics", schema="school")

    op.drop_index("ix_exam_syllabi_is_active", table_name="exam_syllabi", schema="school")
    op.drop_index("ix_exam_syllabi_name", table_name="exam_syllabi", schema="school")
    op.drop_table("exam_syllabi", schema="school")
