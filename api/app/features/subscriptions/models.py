"""ORM models for Subscription Tiers, Subscriptions, and Payments — T-022.

Schema-only at launch: no Stripe webhook handlers, no billing SDK imports.
Stripe IDs are stored as nullable varchar columns for future integration only.
Per ARCH §3.17: all payment processing is deferred to Phase 2.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class SubscriberType(StrEnum):
    """Who a tier/subscription applies to."""

    DISTRICT = "district"
    SCHOOL = "school"


class SubscriptionStatus(StrEnum):
    """Lifecycle state of a subscription."""

    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(StrEnum):
    """Outcome of a payment ledger entry."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Native Postgres enum bound to the school schema (ARCH §4.4 — stable value sets).

    values_callable pins the stored labels to the StrEnum *values* (not member names);
    create_type=False keeps DDL emission with the Alembic migration (matches User.role).
    """
    return SAEnum(
        enum_cls,
        name=name,
        schema="school",
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,
    )


class SubscriptionTier(AuditMixin, SoftDeleteMixin, Base):
    """Pricing tier catalogue entry (e.g. Starter, Pro, Enterprise).

    applies_to constrains which subscriber type can be assigned this tier.
    caps is a JSON bag of feature limits (e.g. {"max_students": 200, "ai_sessions": 1000}).
    """

    __tablename__ = "subscription_tiers"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Determines which subscriber type can use this tier
    applies_to: Mapped[SubscriberType] = mapped_column(
        _pg_enum(SubscriberType, "subscription_tiers_applies_to_enum"), nullable=False
    )
    pricing_monthly_pkr: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Feature caps stored as JSONB; null means unlimited / no caps defined yet
    caps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class Subscription(AuditMixin, Base):
    """Active subscription record linking a subscriber to a tier.

    subscriber_type is "district" or "school"; subscriber_id is the corresponding ID.
    stripe_subscription_id is nullable — populated only when Stripe integration ships.
    """

    __tablename__ = "subscriptions"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # RESTRICT: a tier in use must not be deleted out from under live subscriptions.
    tier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.subscription_tiers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subscriber_type: Mapped[SubscriberType] = mapped_column(
        _pg_enum(SubscriberType, "subscriptions_subscriber_type_enum"), nullable=False
    )
    subscriber_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        _pg_enum(SubscriptionStatus, "subscriptions_status_enum"),
        nullable=False,
        default=SubscriptionStatus.PENDING,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Reserved for Phase 2 Stripe integration; not used at launch
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SubscriptionPayment(AuditMixin, Base):
    """Immutable payment ledger entry for a subscription.

    stripe_payment_intent_id is nullable — populated only when Stripe integration ships.
    status: pending | succeeded | failed | refunded.
    """

    __tablename__ = "subscription_payments"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # CASCADE: payment ledger rows belong to their subscription's lifecycle.
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_pkr: Mapped[int] = mapped_column(Integer, nullable=False)
    # Reserved for Phase 2 Stripe integration
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        _pg_enum(PaymentStatus, "subscription_payments_status_enum"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
