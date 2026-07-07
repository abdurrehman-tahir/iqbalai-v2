"""Exam-framework notification templates (T-097, Flow 4 §3.5).

Framework events reuse existing locked §9.21 namespaces (no new namespace): Platform-Admin
alerts go under ``system``; the student "updated version available" notice goes under
``self_study``. The template-key prefix IS the namespace (e.g. ``system.framework_...``),
so the dispatcher derives the namespace from the key.

All keys carry en/ur/sd/ps (Acceptance #5 — no ``__TODO__``). Bodies use ``{param}``
placeholders filled by ``render_framework_template``.
"""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

FRAMEWORK_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "system.framework_pending_approval": {
        "default": {
            "en": {
                "title": "Framework ready for review",
                "body": 'The study plan for "{framework_name}" has finished AI research and is ready for your approval.',
            },
            "ur": {
                "title": "فریم ورک جائزے کے لیے تیار ہے",
                "body": '"{framework_name}" کا مطالعاتی منصوبہ AI ریسرچ مکمل کر چکا ہے اور آپ کی منظوری کے لیے تیار ہے۔',
            },
            "sd": {
                "title": "فريم ورڪ جائزي لاءِ تيار آهي",
                "body": '"{framework_name}" جو مطالعي جو منصوبو AI ريسرچ مڪمل ڪري چڪو آهي ۽ توهان جي منظوري لاءِ تيار آهي۔',
            },
            "ps": {
                "title": "چوکاټ د بیاکتنې لپاره چمتو دی",
                "body": 'د "{framework_name}" د زده‌کړې پلان د AI څیړنه بشپړه کړه او ستاسو د تصویب لپاره چمتو دی۔',
            },
        }
    },
    "system.framework_approval_reminder": {
        "default": {
            "en": {
                "title": "Framework approval pending",
                "body": '"{framework_name}" has been awaiting approval for {days} days. Please review it.',
            },
            "ur": {
                "title": "فریم ورک کی منظوری زیر التوا",
                "body": '"{framework_name}" کو منظوری کا انتظار {days} دن سے ہے۔ براہ کرم اس کا جائزہ لیں۔',
            },
            "sd": {
                "title": "فريم ورڪ جي منظوري رکيل آهي",
                "body": '"{framework_name}" کي منظوري جو انتظار {days} ڏينهن کان آهي۔ مهرباني ڪري ان جو جائزو وٺو۔',
            },
            "ps": {
                "title": "د چوکاټ تصویب پاتې دی",
                "body": 'د "{framework_name}" تصویب {days} ورځې انتظار کوي۔ مهرباني وکړئ بیاکتنه یې وکړئ۔',
            },
        }
    },
    "system.framework_approval_escalated": {
        "default": {
            "en": {
                "title": "Framework approval overdue",
                "body": '"{framework_name}" has been awaiting approval for {days} days and needs urgent attention.',
            },
            "ur": {
                "title": "فریم ورک کی منظوری میں تاخیر",
                "body": '"{framework_name}" کو منظوری کا انتظار {days} دن سے ہے اور اسے فوری توجہ درکار ہے۔',
            },
            "sd": {
                "title": "فريم ورڪ جي منظوري ۾ دير",
                "body": '"{framework_name}" کي منظوري جو انتظار {days} ڏينهن کان آهي ۽ ان کي فوري ڌيان گهرجي۔',
            },
            "ps": {
                "title": "د چوکاټ تصویب ناوخته شو",
                "body": 'د "{framework_name}" تصویب {days} ورځې انتظار کوي او بیړنۍ پاملرنې ته اړتیا لري۔',
            },
        }
    },
    "self_study.framework_version_available": {
        "default": {
            "en": {
                "title": "Updated study plan available",
                "body": '"{framework_name}" has an updated study plan (v{version}). Review the changes and switch when you are ready.',
            },
            "ur": {
                "title": "نیا مطالعاتی منصوبہ دستیاب",
                "body": '"{framework_name}" کا نیا مطالعاتی منصوبہ (v{version}) دستیاب ہے۔ تبدیلیوں کا جائزہ لیں اور تیار ہونے پر تبدیل کریں۔',
            },
            "sd": {
                "title": "نئون مطالعي جو منصوبو موجود",
                "body": '"{framework_name}" جو نئون مطالعي جو منصوبو (v{version}) موجود آهي۔ تبديلين جو جائزو وٺو ۽ تيار ٿيڻ تي تبديل ڪريو۔',
            },
            "ps": {
                "title": "تازه شوی د زده‌کړې پلان شتون لري",
                "body": 'د "{framework_name}" تازه شوی د زده‌کړې پلان (v{version}) شتون لري۔ بدلونونه وګورئ او کله چې چمتو یاست بدل یې کړئ۔',
            },
        }
    },
}

# Every framework template is in-app (no email tier for M-07; see account.py for email).
TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    key: frozenset({"in_app"}) for key in FRAMEWORK_TEMPLATES
}


def render_framework_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    if template_key not in FRAMEWORK_TEMPLATES:
        raise KeyError(f"Unknown framework template: {template_key}")

    variants = FRAMEWORK_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
