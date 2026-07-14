"""Self-study namespace notification templates — Flow 8 / T-083."""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

SELF_STUDY_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "self_study.exam_countdown": {
        "default": {
            "en": {
                "title": "Exam approaching",
                "body": "Your exam is in {days_remaining} days ({exam_date}). Keep your study plan on track.",  # noqa: E501
            },
            "ur": {
                "title": "امتحان قریب ہے",
                "body": "آپ کا امتحان {days_remaining} دنوں میں ہے ({exam_date})۔ اپنے مطالعے کا شیڈول برقرار رکھیں۔",  # noqa: E501
            },
            "sd": {
                "title": "امتحان ويجه آهي",
                "body": "توهان جو امتحان {days_remaining} ڏينهنن ۾ آهي ({exam_date})۔ پنهنجي پڙهائي جو منصوبو جاري رکو۔",  # noqa: E501
            },
            "ps": {
                "title": "امتحان نږدې دی",
                "body": "ستاسو امتحان په {days_remaining} ورځو کې دی ({exam_date})۔ خپل مطالعې پلان پر مخ وړئ۔",  # noqa: E501
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    "self_study.exam_countdown": frozenset({"in_app"}),
}


def render_self_study_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    if template_key not in SELF_STUDY_TEMPLATES:
        raise KeyError(f"Unknown self_study template: {template_key}")

    variants = SELF_STUDY_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
