"""Content library namespace notification templates — Flow 3 §7 / T-065."""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

CONTENT_LIBRARY_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "content_library.item_available": {
        "default": {
            "en": {
                "title": "Library item ready",
                "body": 'Your upload "{title}" ({content_type}) is now available in the school library.',
            },
            "ur": {
                "title": "لائبریری مواد تیار",
                "body": 'آپ کی اپ لوڈ "{title}" ({content_type}) اب اسکول لائبریری میں دستیاب ہے۔',
            },
            "sd": {
                "title": "لائبريري مواد تيار",
                "body": 'توهان جي اپ لوڊ "{title}" ({content_type}) هاڻي اسڪول لائبريري ۾ موجود آهي۔',
            },
            "ps": {
                "title": "د کتابتون توکي چمتو",
                "body": 'ستاسو پورته "{title}" ({content_type}) اوس په ښوونځي کتابتون کې شتون لري۔',
            },
        }
    },
    "content_library.item_failed": {
        "default": {
            "en": {
                "title": "Library ingestion failed",
                "body": 'Ingestion failed for "{title}": {error}',
            },
            "ur": {
                "title": "لائبریری انجestion ناکام",
                "body": '"{title}" کے لیے ingestion ناکام: {error}',
            },
            "sd": {
                "title": "لائبريري انجيسشن ناڪام",
                "body": '"{title}" لاءِ انجيسشن ناڪام: {error}',
            },
            "ps": {
                "title": "د کتابتون پروسس ناکام",
                "body": 'د "{title}" پروسس ناکام: {error}',
            },
        }
    },
    "content_library.item_published": {
        "default": {
            "en": {
                "title": "New reference in school library",
                "body": '{actor_name} shared "{title}" with the school library.',
            },
            "ur": {
                "title": "اسکول لائبریری میں نیا حوالہ",
                "body": '{actor_name} نے "{title}" اسکول لائبریری میں شیئر کیا۔',
            },
            "sd": {
                "title": "اسڪول لائبريري ۾ نئون حوالو",
                "body": '{actor_name} "{title}" اسڪول لائبريري ۾ شيئر ڪيو۔',
            },
            "ps": {
                "title": "په ښوونځي کتابتون کې نوی حواله",
                "body": '{actor_name} "{title}" په ښوونځي کتابتون کې شریک کړ۔',
            },
        },
        "publisher": {
            "en": {
                "title": "Reference published",
                "body": 'You published "{title}" to the school library.',
            },
            "ur": {
                "title": "حوالہ شائع ہو گیا",
                "body": 'آپ نے "{title}" اسکول لائبریری میں شائع کیا۔',
            },
            "sd": {
                "title": "حوالو شايع ٿيو",
                "body": 'توهان "{title}" اسڪول لائبريري ۾ شايع ڪيو۔',
            },
            "ps": {
                "title": "حواله خپور شو",
                "body": 'تاسو "{title}" په ښوونځي کتابتون کې خپور کړ۔',
            },
        },
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    "content_library.item_available": frozenset({"in_app"}),
    "content_library.item_failed": frozenset({"in_app"}),
    "content_library.item_published": frozenset({"in_app"}),
}


def render_content_library_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return rendered title/body for a content_library template key and locale."""
    if template_key not in CONTENT_LIBRARY_TEMPLATES:
        raise KeyError(f"Unknown content_library template: {template_key}")

    variants = CONTENT_LIBRARY_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
