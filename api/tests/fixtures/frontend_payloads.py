"""Payloads the admin UI sends after Phase 2 contract alignment."""

from __future__ import annotations

from typing import Any

# SyllabiClient → syllabiApi.create
EXAM_SYLLABUS_CREATE_FROM_UI: dict[str, Any] = {
    "name": "Matric Punjab Board",
    "exam_board": "Punjab Board",
    "language": "en",
}

# SubscriptionTiersClient → subscriptionsApi.create
SUBSCRIPTION_TIER_CREATE_FROM_UI: dict[str, Any] = {
    "name": "School Basic",
    "slug": "school-basic",
    "applies_to": "school",
    "pricing_monthly_pkr": 5000,
    "caps": {},
}
