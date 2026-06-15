"""Account notification template tests — T-038."""

from __future__ import annotations

import pytest

from app.infrastructure.notifications.templates.account import (
    ACCOUNT_TEMPLATES,
    SUPPORTED_LOCALES,
    TEMPLATE_CHANNELS,
    render_account_template,
)

EXPECTED_KEYS = frozenset(
    {
        "account.invite_sent",
        "account.invite_expired",
        "account.invite_accepted",
        "account.suspended",
        "account.reactivated",
        "account.deactivated",
        "account.bulk_import_done",
    }
)


@pytest.mark.parametrize("template_key", sorted(EXPECTED_KEYS))
def test_all_template_keys_registered(template_key: str) -> None:
    assert template_key in ACCOUNT_TEMPLATES
    assert template_key in TEMPLATE_CHANNELS


@pytest.mark.parametrize("template_key", sorted(EXPECTED_KEYS))
@pytest.mark.parametrize("locale", sorted(SUPPORTED_LOCALES))
def test_templates_render_in_all_locales(template_key: str, locale: str) -> None:
    params = {
        "inviter_name": "Admin",
        "invite_url": "https://app.example/accept",
        "email": "user@test.com",
        "name": "User One",
        "role": "teacher",
        "total_rows": "50",
        "success_rows": "48",
        "failed_rows": "2",
    }
    variant = "default"
    if template_key == "account.suspended":
        for variant in ("target", "actor"):
            rendered = render_account_template(
                template_key, locale=locale, variant=variant, params=params
            )
            assert rendered["title"]
            assert rendered["body"]
        return
    if template_key == "account.reactivated":
        for variant in ("target", "actor"):
            rendered = render_account_template(
                template_key, locale=locale, variant=variant, params=params
            )
            assert rendered["title"]
            assert rendered["body"]
        return

    rendered = render_account_template(
        template_key, locale=locale, variant=variant, params=params
    )
    assert rendered["title"]
    assert rendered["body"]
    if template_key in {"account.invite_sent", "account.reactivated", "account.deactivated"}:
        assert rendered.get("subject")
