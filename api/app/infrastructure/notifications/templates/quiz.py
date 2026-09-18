"""Quiz-namespace notification templates (T-149; ARCH §9.21 ``quiz``)."""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

QUIZ_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "quiz.available": {
        "default": {
            "en": {
                "title": "Quiz available",
                "body": 'Your quiz for "{topic}" is ready — take it when you can.',
            },
            "ur": {
                "title": "کوئز دستیاب ہے",
                "body": '"{topic}" کے لیے آپ کا کوئز تیار ہے — جب چاہیں حل کریں۔',
            },
            "sd": {
                "title": "ڪوئز موجود آهي",
                "body": '"{topic}" لاءِ توهان جو ڪوئز تيار آهي — جڏهن چاهيو حل ڪريو۔',
            },
            "ps": {
                "title": "کوئز شتون لري",
                "body": 'ستاسو د "{topic}" کوئز چمتو دی — کله چې وغواړئ یې حل کړئ۔',
            },
        }
    },
    "quiz.results_ready": {
        "default": {
            "en": {
                "title": "Quiz results ready",
                "body": 'Students have completed the quiz for "{topic}". View class results.',
            },
            "ur": {
                "title": "کوئز نتائج تیار",
                "body": 'طلبہ نے "{topic}" کا کوئز مکمل کر لیا۔ جماعت کے نتائج دیکھیں۔',
            },
            "sd": {
                "title": "ڪوئز جا نتيجا تيار",
                "body": 'شاگردن "{topic}" جو ڪوئز مڪمل ڪيو۔ ڪلاس جا نتيجا ڏسو۔',
            },
            "ps": {
                "title": "د کوئز پایلې چمتو دي",
                "body": 'زده کوونکو د "{topic}" کوئز بشپړ کړ۔ د ټولګي پایلې وګورئ۔',
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    key: frozenset({"in_app"}) for key in QUIZ_TEMPLATES
}


def render_quiz_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    if template_key not in QUIZ_TEMPLATES:
        raise KeyError(f"Unknown quiz template: {template_key}")

    variants = QUIZ_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
