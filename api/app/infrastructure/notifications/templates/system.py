"""System-namespace notification templates (T-135, ARCH §9.21).

Scoped to the one template key this ticket's acceptance criteria requires —
a Platform-Admin-only plagiarism flag alert. The body deliberately carries no
identifying detail (no teacher name, no lecture title) — the flag row itself
(``lecture_plagiarism_flags``) holds the identifiers for admin triage; the
notification is just the "something needs review" nudge (Flow 5 §3.7 privacy
rule: matched-teacher identity is never exposed, including here).

All keys carry en/ur/sd/ps (matches the ``lectures`` namespace convention —
Platform Admins use the same locale-scoped app as everyone else).
"""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

SYSTEM_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "system.plagiarism_flagged": {
        "default": {
            "en": {
                "title": "Originality flag raised",
                "body": (
                    "A lecture version scored below the originality threshold "
                    "({similarity_pct}% similarity to existing content) and needs review."
                ),
            },
            "ur": {
                "title": "اصلیت کا انتباہ",
                "body": (
                    "ایک لیکچر ورژن اصلیت کی حد سے کم رہا "
                    "({similarity_pct}% موجودہ مواد سے مماثلت) اور جائزے کا محتاج ہے۔"
                ),
            },
            "sd": {
                "title": "اصليت جو الرٽ",
                "body": (
                    "هڪ ليڪچر ورجن اصليت جي حد کان گهٽ رهيو "
                    "({similarity_pct}% موجود مواد سان مماثلت) ۽ جائزي جو محتاج آهي۔"
                ),
            },
            "ps": {
                "title": "د اصالت خبرتیا",
                "body": (
                    "یو د لیکچر نسخه د اصالت له حد نه ټیټ ښکاره شو "
                    "({similarity_pct}% د شتون مینځپانګې سره ورته والی) او بیاکتنې ته اړتیا لري۔"
                ),
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    key: frozenset({"in_app"}) for key in SYSTEM_TEMPLATES
}


def render_system_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return rendered title/body for a system template key and locale."""
    if template_key not in SYSTEM_TEMPLATES:
        raise KeyError(f"Unknown system template: {template_key}")

    variants = SYSTEM_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
