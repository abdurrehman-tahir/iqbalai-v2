"""System-namespace notification template tests — T-135."""

from __future__ import annotations

import pytest

from app.infrastructure.notifications.templates.system import (
    SUPPORTED_LOCALES,
    SYSTEM_TEMPLATES,
    render_system_template,
)


def test_render_plagiarism_flagged_interpolates_similarity() -> None:
    rendered = render_system_template(
        "system.plagiarism_flagged", locale="en", params={"similarity_pct": "93"}
    )
    assert "93" in rendered["body"]
    assert rendered["title"]


def test_render_falls_back_to_default_locale_for_unsupported() -> None:
    rendered = render_system_template(
        "system.plagiarism_flagged", locale="fr", params={"similarity_pct": "90"}
    )
    en_rendered = render_system_template(
        "system.plagiarism_flagged", locale="en", params={"similarity_pct": "90"}
    )
    assert rendered == en_rendered


def test_render_raises_for_unknown_template() -> None:
    with pytest.raises(KeyError):
        render_system_template("system.does_not_exist")


def test_all_locales_present_for_every_template() -> None:
    """No __TODO__-style gaps — every locked locale has a real translation."""
    for template_key, variants in SYSTEM_TEMPLATES.items():
        for variant_name, locales in variants.items():
            assert (
                set(locales) == SUPPORTED_LOCALES
            ), f"{template_key}/{variant_name} missing a locale"
            for locale, fields in locales.items():
                assert fields["title"], f"{template_key}/{variant_name}/{locale} empty title"
                assert fields["body"], f"{template_key}/{variant_name}/{locale} empty body"
