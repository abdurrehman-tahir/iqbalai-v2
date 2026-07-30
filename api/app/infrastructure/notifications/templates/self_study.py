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
    "self_study.exam_passed": {
        "default": {
            "en": {
                "title": "Set a new exam date",
                "body": "Your exam date ({exam_date}) has passed. Update your exam date to keep pacing on track.",  # noqa: E501
            },
            "ur": {
                "title": "نیا امتحان کی تاریخ مقرر کریں",
                "body": "آپ کی امتحان کی تاریخ ({exam_date}) گزر چکی ہے۔ شیڈول برقرار رکھنے کے لیے نئی تاریخ مقرر کریں۔",  # noqa: E501
            },
            "sd": {
                "title": "نئين امتحان جي تاريخ مقرر ڪريو",
                "body": "توهان جي امتحان جي تاريخ ({exam_date}) گذري چڪي آهي۔ منصوبو جاري رکڻ لاءِ نئين تاريخ مقرر ڪريو۔",  # noqa: E501
            },
            "ps": {
                "title": "نوې د امتحان نېټه وټاکئ",
                "body": "ستاسو د امتحان نېټه ({exam_date}) تېره شوې ده۔ د پلان ساتلو لپاره نوې نېټه وټاکئ۔",  # noqa: E501
            },
        }
    },
    "self_study.diagnostic_available": {
        "default": {
            "en": {
                "title": "Diagnostic available",
                "body": "You are ready to take a short diagnostic. It helps us suggest focus areas — never a grade.",  # noqa: E501
            },
            "ur": {
                "title": "تشخیصی ٹیسٹ دستیاب ہے",
                "body": "آپ ایک مختصر تشخیصی ٹیسٹ دے سکتے ہیں۔ یہ توجہ کے شعبے بتاتا ہے — کبھی بھی نمبر نہیں۔",  # noqa: E501
            },
            "sd": {
                "title": "تشخيصي ٽيسٽ موجود آهي",
                "body": "توهان مختصر تشخيصي ٽيسٽ وٺي سگهو ٿا۔ اهو ڌيان جا علائقا ٻڌائي ٿو — ڪڏهن به نمبر نه۔",  # noqa: E501
            },
            "ps": {
                "title": "تشخیصي ازموینه شته",
                "body": "تاسو یوه لنډه تشخیصي ازموینه اخیستلی شئ۔ دا د تمرکز ساحې وړاندیز کوي — هیڅکله نمره نه.",  # noqa: E501
            },
        }
    },
    "self_study.diagnostic_completed": {
        "default": {
            "en": {
                "title": "Diagnostic complete — focus areas",
                "body": "Nice work. Areas to focus on: {focus_areas}. This is coaching guidance, not a grade or score.",  # noqa: E501
            },
            "ur": {
                "title": "تشخیص مکمل — توجہ کے شعبے",
                "body": "اچھا کام۔ توجہ دیں: {focus_areas}۔ یہ رہنمائی ہے، نمبر یا اسکور نہیں۔",  # noqa: E501
            },
            "sd": {
                "title": "تشخيص مڪمل — ڌيان جا علائقا",
                "body": "سٺو ڪم۔ ڌيان ڏيو: {focus_areas}۔ هي رهنمائي آهي، نمبر يا اسڪور نه۔",  # noqa: E501
            },
            "ps": {
                "title": "تشخیص بشپړه — د تمرکز ساحې",
                "body": "ښه کار. تمرکز وکړئ: {focus_areas}. دا لارښوونه ده، نمره یا سکور نه.",  # noqa: E501
            },
        }
    },
    "self_study.diagnostic_retake_available": {
        "default": {
            "en": {
                "title": "Diagnostic retake available",
                "body": "It has been 30 days since your last diagnostic. You can retake it to refresh your focus areas.",  # noqa: E501
            },
            "ur": {
                "title": "دوبارہ تشخیص دستیاب ہے",
                "body": "آخری تشخیص کے بعد ۳۰ دن گزر چکے ہیں۔ آپ توجہ کے شعبے تازہ کرنے کے لیے دوبارہ دے سکتے ہیں۔",  # noqa: E501
            },
            "sd": {
                "title": "ٻيهر تشخيص موجود آهي",
                "body": "آخري تشخيص کان پوءِ ۳۰ ڏينهن گذري ويا آهن۔ توهان ڌيان جا علائقا تازا ڪرڻ لاءِ ٻيهر وٺي سگهو ٿا۔",  # noqa: E501
            },
            "ps": {
                "title": "بیا تشخیصي ازموینه شته",
                "body": "ستاسو د وروستۍ تشخیصې راهیسې ۳۰ ورځې تېرې شوې. تاسو کولی شئ بیا یې واخلئ ترڅو د تمرکز ساحې تازه کړئ.",  # noqa: E501
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    # in_app only — FCM push / email channel publishers deferred (T-023 / Phase 2).
    "self_study.exam_countdown": frozenset({"in_app"}),
    "self_study.exam_passed": frozenset({"in_app"}),
    "self_study.diagnostic_available": frozenset({"in_app"}),
    "self_study.diagnostic_completed": frozenset({"in_app"}),
    "self_study.diagnostic_retake_available": frozenset({"in_app"}),
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
