"""Promote subscription varchar columns to native Postgres enums (ARCH §4.4).

Revision ID: school_0013
Revises: school_0012
Create Date: 2026-06-10

Purpose: Align school_0007 varchar columns with ORM native enum types.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "school_0013"
down_revision: str = "school_0012"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE school.subscription_tiers_applies_to_enum AS ENUM ('district', 'school')"
    )
    op.execute(
        "CREATE TYPE school.subscriptions_subscriber_type_enum AS ENUM ('district', 'school')"
    )
    op.execute(
        "CREATE TYPE school.subscriptions_status_enum AS ENUM "
        "('pending', 'active', 'past_due', 'cancelled', 'expired')"
    )
    op.execute(
        "CREATE TYPE school.subscription_payments_status_enum AS ENUM "
        "('pending', 'succeeded', 'failed', 'refunded')"
    )

    op.execute(
        "ALTER TABLE school.subscription_tiers "
        "ALTER COLUMN applies_to TYPE school.subscription_tiers_applies_to_enum "
        "USING applies_to::school.subscription_tiers_applies_to_enum"
    )
    op.execute(
        "ALTER TABLE school.subscriptions "
        "ALTER COLUMN subscriber_type TYPE school.subscriptions_subscriber_type_enum "
        "USING subscriber_type::school.subscriptions_subscriber_type_enum"
    )
    op.execute("ALTER TABLE school.subscriptions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE school.subscriptions "
        "ALTER COLUMN status TYPE school.subscriptions_status_enum "
        "USING status::school.subscriptions_status_enum"
    )
    op.execute(
        "ALTER TABLE school.subscriptions "
        "ALTER COLUMN status SET DEFAULT 'pending'::school.subscriptions_status_enum"
    )
    op.execute("ALTER TABLE school.subscription_payments ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE school.subscription_payments "
        "ALTER COLUMN status TYPE school.subscription_payments_status_enum "
        "USING status::school.subscription_payments_status_enum"
    )
    op.execute(
        "ALTER TABLE school.subscription_payments "
        "ALTER COLUMN status SET DEFAULT 'pending'::school.subscription_payments_status_enum"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE school.subscription_payments "
        "ALTER COLUMN status TYPE character varying(20) "
        "USING status::text"
    )
    op.execute(
        "ALTER TABLE school.subscriptions "
        "ALTER COLUMN status TYPE character varying(20) "
        "USING status::text"
    )
    op.execute(
        "ALTER TABLE school.subscriptions "
        "ALTER COLUMN subscriber_type TYPE character varying(20) "
        "USING subscriber_type::text"
    )
    op.execute(
        "ALTER TABLE school.subscription_tiers "
        "ALTER COLUMN applies_to TYPE character varying(20) "
        "USING applies_to::text"
    )

    op.execute("DROP TYPE IF EXISTS school.subscription_payments_status_enum")
    op.execute("DROP TYPE IF EXISTS school.subscriptions_status_enum")
    op.execute("DROP TYPE IF EXISTS school.subscriptions_subscriber_type_enum")
    op.execute("DROP TYPE IF EXISTS school.subscription_tiers_applies_to_enum")
