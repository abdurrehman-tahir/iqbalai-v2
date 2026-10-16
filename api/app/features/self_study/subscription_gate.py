"""Subscription gate placeholder for self-study (Flow 8 §3.1 / Flow 13).

At launch limits are unset — every check is a no-op allow. Schema hooks live on
``study_plans.subscription_tier_id``. Enforcement lands in M-23.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelfStudySubscriptionLimits:
    """Unset ⇒ no-op. Future M-23 fills these from subscription_tiers."""

    max_active_plans: int | None = None
    max_monthly_uploads: int | None = None


@dataclass(frozen=True, slots=True)
class SelfStudySubscriptionGateResult:
    enforced: bool
    allowed: bool
    limits: SelfStudySubscriptionLimits
    reason: str | None = None


def check_self_study_subscription_limits(
    *,
    active_plan_count: int = 0,
    monthly_upload_count: int = 0,
    limits: SelfStudySubscriptionLimits | None = None,
) -> SelfStudySubscriptionGateResult:
    """Return allow when limits are unset (launch default).

    ``active_plan_count`` / ``monthly_upload_count`` are accepted so call sites
    can pass live counts without branching when M-23 turns enforcement on.
    """
    resolved = limits or SelfStudySubscriptionLimits()
    _ = (active_plan_count, monthly_upload_count)  # reserved for M-23
    if resolved.max_active_plans is None and resolved.max_monthly_uploads is None:
        return SelfStudySubscriptionGateResult(
            enforced=False,
            allowed=True,
            limits=resolved,
            reason=None,
        )
    # Future path — not reached until M-23 sets limits.
    if resolved.max_active_plans is not None and active_plan_count >= resolved.max_active_plans:
        return SelfStudySubscriptionGateResult(
            enforced=True,
            allowed=False,
            limits=resolved,
            reason="max_active_plans",
        )
    if (
        resolved.max_monthly_uploads is not None
        and monthly_upload_count >= resolved.max_monthly_uploads
    ):
        return SelfStudySubscriptionGateResult(
            enforced=True,
            allowed=False,
            limits=resolved,
            reason="max_monthly_uploads",
        )
    return SelfStudySubscriptionGateResult(
        enforced=True,
        allowed=True,
        limits=resolved,
        reason=None,
    )
