"""Lecture-generation notification templates (T-126, flow-5 §7).

Scoped to the three template keys this ticket's acceptance criteria actually
require — generation complete / failed / timeout. The spec's full ``lectures``
namespace table also lists ``generation_started``, ``published``, ``linked``,
etc.; those belong to other tickets (or are out of this ticket's "What this
ticket builds" scope) and are not built here.

All keys carry en/ur/sd/ps (Acceptance #4 — no ``__TODO__``). Bodies use
``{param}`` placeholders filled by ``render_lecture_template``. Every template
is in-app only for now — push/email are declared in the spec table but no
FCM/email transport exists yet (Phase 2 stub, same scope decision as
``notifications/templates/framework.py``).
"""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

LECTURE_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "lectures.generation_complete": {
        "default": {
            "en": {
                "title": "Lecture ready",
                "body": 'Your lecture on "{topic}" has finished generating and is ready to review.',
            },
            "ur": {
                "title": "لیکچر تیار ہے",
                "body": '"{topic}" پر آپ کا لیکچر تیار ہو گیا ہے اور جائزے کے لیے دستیاب ہے۔',
            },
            "sd": {
                "title": "ليڪچر تيار آهي",
                "body": '"{topic}" تي توهان جو ليڪچر تيار ٿي ويو آهي ۽ جائزي لاءِ موجود آهي۔',
            },
            "ps": {
                "title": "لیکچر چمتو دی",
                "body": 'ستاسو د "{topic}" په اړه لیکچر جوړ شو او د بیاکتنې لپاره چمتو دی۔',
            },
        }
    },
    "lectures.generation_failed": {
        "default": {
            "en": {
                "title": "Lecture generation failed",
                "body": 'Something went wrong while generating your lecture on "{topic}". Please try again.',
            },
            "ur": {
                "title": "لیکچر تیار کرنے میں ناکامی",
                "body": '"{topic}" پر لیکچر تیار کرتے وقت مسئلہ پیش آیا۔ براہ کرم دوبارہ کوشش کریں۔',
            },
            "sd": {
                "title": "ليڪچر تيار ڪرڻ ۾ ناڪامي",
                "body": '"{topic}" تي ليڪچر تيار ڪندي مسئلو پيش آيو۔ مهرباني ڪري ٻيهر ڪوشش ڪريو۔',
            },
            "ps": {
                "title": "د لیکچر جوړول ناکام شول",
                "body": 'ستاسو د "{topic}" لیکچر په جوړولو کې ستونزه رامنځته شوه۔ مهرباني وکړئ بیا هڅه وکړئ۔',
            },
        }
    },
    "lectures.generation_timeout": {
        "default": {
            "en": {
                "title": "Lecture generation timed out",
                "body": 'Generating your lecture on "{topic}" took too long and timed out. Please try again.',
            },
            "ur": {
                "title": "لیکچر تیار کرنے کا وقت ختم",
                "body": '"{topic}" پر لیکچر تیار کرنے میں وقت زیادہ لگا اور یہ ختم ہو گیا۔ براہ کرم دوبارہ کوشش کریں۔',
            },
            "sd": {
                "title": "ليڪچر تيار ڪرڻ جو وقت ختم",
                "body": '"{topic}" تي ليڪچر تيار ڪرڻ ۾ گهڻو وقت لڳو ۽ اهو ختم ٿي ويو۔ مهرباني ڪري ٻيهر ڪوشش ڪريو۔',
            },
            "ps": {
                "title": "د لیکچر جوړولو مهال ختم شو",
                "body": 'ستاسو د "{topic}" لیکچر جوړول ډیر وخت ونیو او ختم شو۔ مهرباني وکړئ بیا هڅه وکړئ۔',
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    key: frozenset({"in_app"}) for key in LECTURE_TEMPLATES
}


def render_lecture_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return rendered title/body for a lectures template key and locale."""
    if template_key not in LECTURE_TEMPLATES:
        raise KeyError(f"Unknown lectures template: {template_key}")

    variants = LECTURE_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
