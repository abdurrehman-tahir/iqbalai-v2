"""Connections namespace notification templates — Flow 4 §7 / T-081."""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

CONNECTIONS_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "connections.parent_link_pending": {
        "default": {
            "en": {
                "title": "Parent link request",
                "body": "{parent_name} requested to link to your account. Review and approve if you know this person.",
            },
            "ur": {
                "title": "والدین لنک کی درخواست",
                "body": "{parent_name} نے آپ کے اکاؤنٹ سے لنک کرنے کی درخواست کی ہے۔ اگر آپ اس شخص کو جانتے ہیں تو منظور کریں۔",
            },
            "sd": {
                "title": "والدين لنڪ درخواست",
                "body": "{parent_name} توهان جي اڪائونٽ سان لنڪ ڪرڻ جي درخواست ڪئي آهي۔ جيڪڏهن توهان هن شخص کي ڃاڻو ٿا ته منظور ڪريو۔",
            },
            "ps": {
                "title": "د والدین د نښلولو غوښتنه",
                "body": "{parent_name} ستاسو حساب سره د نښلولو غوښتنه کړې ده۔ که تاسو دا کس پیژنئ، تصویب یې کړئ۔",
            },
        }
    },
    "connections.parent_link_approved": {
        "default": {
            "en": {
                "title": "Parent link approved",
                "body": "{student_name} approved your link request. You now have read-only access to their account.",
            },
            "ur": {
                "title": "والدین لنک منظور",
                "body": "{student_name} نے آپ کی لنک درخواست منظور کر لی ہے۔ اب آپ کے پاس ان کے اکاؤنٹ تک صرف پڑھنے کی رسائی ہے۔",
            },
            "sd": {
                "title": "والدين لنڪ منظور",
                "body": "{student_name} توهان جي لنڪ درخواست منظور ڪئي آهي۔ هاڻي توهان کي ان جي اڪائونٽ تائين صرف پڙهڻ جي رسائي آهي۔",
            },
            "ps": {
                "title": "د والدین نښلول تصویب شول",
                "body": "{student_name} ستاسو د نښلولو غوښتنه تصویب کړه۔ اوس تاسو یوازې د دوی حساب لوستلای شئ۔",
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    "connections.parent_link_pending": frozenset({"in_app"}),
    "connections.parent_link_approved": frozenset({"in_app"}),
}


def render_connections_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    if template_key not in CONNECTIONS_TEMPLATES:
        raise KeyError(f"Unknown connections template: {template_key}")

    variants = CONNECTIONS_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
