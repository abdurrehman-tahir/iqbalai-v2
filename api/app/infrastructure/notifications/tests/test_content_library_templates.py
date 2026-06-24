"""Content library notification template tests — T-065."""

from __future__ import annotations

import pytest

from app.infrastructure.notifications.templates.content_library import (
    CONTENT_LIBRARY_TEMPLATES,
    SUPPORTED_LOCALES,
    TEMPLATE_CHANNELS,
    render_content_library_template,
)

EXPECTED_KEYS = frozenset(
    {
        "content_library.item_available",
        "content_library.item_failed",
        "content_library.item_published",
    }
)


@pytest.mark.parametrize("template_key", sorted(EXPECTED_KEYS))
def test_all_template_keys_registered(template_key: str) -> None:
    assert template_key in CONTENT_LIBRARY_TEMPLATES
    assert template_key in TEMPLATE_CHANNELS


@pytest.mark.parametrize("template_key", sorted(EXPECTED_KEYS))
@pytest.mark.parametrize("locale", sorted(SUPPORTED_LOCALES))
def test_templates_render_in_all_locales(template_key: str, locale: str) -> None:
    params = {
        "title": "Physics Notes",
        "content_type": "reference",
        "error": "MinIO down",
        "actor_name": "Teacher Ali",
    }
    if template_key == "content_library.item_published":
        for variant in ("default", "publisher"):
            rendered = render_content_library_template(
                template_key, locale=locale, variant=variant, params=params
            )
            assert rendered["title"]
            assert rendered["body"]
        return

    rendered = render_content_library_template(
        template_key, locale=locale, params=params
    )
    assert rendered["title"]
    assert rendered["body"]
