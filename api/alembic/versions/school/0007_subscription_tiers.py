"""Add subscription_tiers, subscriptions, subscription_payments (T-022).

Schema-only at launch. No Stripe code. Per ARCH §3.17.

Revision ID: school_0007
Revises: school_0006
Create Date: 2026-05-26


Purpose: Add subscription tiers and related billing tables.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "school_0007"
down_revision: str = "school_0006"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    # ── subscription_tiers ────────────────────────────────────────────────────
    # Platform Admin CRUD only. No enforcement at launch (Phase 2 per ARCH §3.17).
    op.create_table(
        "subscription_tiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        # Applies to: "district" | "school"
        sa.Column("applies_to", sa.String(20), nullable=False),
        sa.Column("pricing_monthly_pkr", sa.Integer, nullable=False, server_default="0"),
        # Free-form capability caps as JSONB (e.g. {"max_students": 500, "ai_calls": 10000})
        sa.Column("caps", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index("ix_subscription_tiers_slug", "subscription_tiers", ["slug"], schema="school")

    # ── subscriptions ─────────────────────────────────────────────────────────
    # Empty at launch. Will be populated when Stripe integration lands (Phase 2).
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tier_id", sa.String(36), nullable=False),
        # subscriber_type: "district" | "school"
        sa.Column("subscriber_type", sa.String(20), nullable=False),
        sa.Column("subscriber_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index(
        "ix_subscriptions_subscriber",
        "subscriptions",
        ["subscriber_type", "subscriber_id"],
        schema="school",
    )

    # ── subscription_payments ─────────────────────────────────────────────────
    # Empty at launch. Populated by Stripe webhook Phase 2 (ARCH §11.20).
    op.create_table(
        "subscription_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        sa.Column("amount_pkr", sa.Integer, nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index(
        "ix_subscription_payments_subscription_id",
        "subscription_payments",
        ["subscription_id"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscription_payments_subscription_id",
        table_name="subscription_payments",
        schema="school",
    )
    op.drop_table("subscription_payments", schema="school")

    op.drop_index("ix_subscriptions_subscriber", table_name="subscriptions", schema="school")
    op.drop_table("subscriptions", schema="school")

    op.drop_index("ix_subscription_tiers_slug", table_name="subscription_tiers", schema="school")
    op.drop_table("subscription_tiers", schema="school")
