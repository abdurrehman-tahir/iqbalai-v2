"""ORM models for Subscription Tiers, Subscriptions, and Payments — T-022.

Schema-only at launch: no Stripe webhook handlers, no billing SDK imports.
Stripe IDs are stored as nullable varchar columns for future integration only.
Per ARCH §3.17: all payment processing is deferred to Phase 2.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


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
    # "district" or "school" — determines which subscriber type can use this tier
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)
    pricing_monthly_pkr: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Feature caps stored as JSON; null means unlimited / no caps defined yet
    caps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    tier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subscriber_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subscriber_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # status: pending | active | past_due | cancelled | expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
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
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount_pkr: Mapped[int] = mapped_column(Integer, nullable=False)
    # Reserved for Phase 2 Stripe integration
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
