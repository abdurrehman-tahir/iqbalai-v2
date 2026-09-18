"""Lecture-generation + edit/scoring notification templates (T-126, T-140;
flow-5 §7, §3.6/§3.10/§3.11).

Originally scoped to generation complete/failed/timeout (T-126); T-140 adds
three more keys for the M-10 edit/scoring loop: ``scoring_complete``
(#32), ``coaching_suggestion`` (Teaching Innovation Record, #36 — no score/
number in the body, per Flow 5 §3.10's locked coaching-framing rule),
``benchmark_updated`` (#37, school tenant only — positively framed, per
§3.11's locked "Top X%, never bottom Y%" rule). All three reuse the
``lectures`` namespace — Flow 5 has these firmly in the lecture edit
lifecycle and adding a new namespace requires a Platform Admin product
decision (ARCH §9.21), not something a ticket does unilaterally. The spec's
full ``lectures`` namespace table also lists ``generation_started``,
``published``, ``linked``, etc.; those belong to other tickets (or are out
of scope here) and are not built here.

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
    "lectures.scoring_complete": {
        "default": {
            "en": {
                "title": "Lecture scored",
                "body": 'Your saved version of "{topic}" scored {total}/{max}. View the breakdown in the version timeline.',
            },
            "ur": {
                "title": "لیکچر کا اسکور تیار",
                "body": '"{topic}" کے محفوظ شدہ ورژن کو {total}/{max} اسکور ملا۔ تفصیل ورژن ٹائم لائن میں دیکھیں۔',
            },
            "sd": {
                "title": "ليڪچر جو اسڪور تيار",
                "body": '"{topic}" جي محفوظ ٿيل ورزن کي {total}/{max} اسڪور مليو۔ تفصيل ورزن ٽائيم لائن ۾ ڏسو۔',
            },
            "ps": {
                "title": "لیکچر ارزول شو",
                "body": 'ستاسو د "{topic}" خوندي شوی نسخه {total}/{max} امتیاز ترلاسه کړ۔ تفصیل د نسخې مهال ویش کې وګورئ۔',
            },
        }
    },
    "lectures.coaching_suggestion": {
        "default": {
            "en": {
                "title": "A tip for you",
                "body": "Your Teaching Innovation Record has a new coaching suggestion.",
            },
            "ur": {
                "title": "آپ کے لیے ایک تجویز",
                "body": "آپ کے ٹیچنگ انوویشن ریکارڈ میں ایک نئی کوچنگ تجویز موجود ہے۔",
            },
            "sd": {
                "title": "توهان لاءِ هڪ صلاح",
                "body": "توهان جي ٽيچنگ انوويشن رڪارڊ ۾ هڪ نئين ڪوچنگ صلاح موجود آهي۔",
            },
            "ps": {
                "title": "تاسو لپاره یوه لار چاره",
                "body": "ستاسو په ښوونې د نوښت ریکارډ کې یوه نوې روزنیزه وړاندیز شتون لري۔",
            },
        }
    },
    "lectures.benchmark_updated": {
        "default": {
            "en": {
                "title": "Your standing updated",
                "body": "Top {percent}% of {subject} teachers in {region} — see your latest standing.",
            },
            "ur": {
                "title": "آپ کی پوزیشن اپ ڈیٹ ہوئی",
                "body": "{region} میں {subject} اساتذہ کے ٹاپ {percent}% میں — اپنی تازہ ترین پوزیشن دیکھیں۔",
            },
            "sd": {
                "title": "توهان جي پوزيشن اپڊيٽ ٿي",
                "body": "{region} ۾ {subject} استادن جي ٽاپ {percent}% ۾ — پنهنجي تازي پوزيشن ڏسو۔",
            },
            "ps": {
                "title": "ستاسو دریځ تازه شو",
                "body": "په {region} کې د {subject} ښوونکو له غوره {percent}٪ څخه — خپل وروستی دریځ وګورئ۔",
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
