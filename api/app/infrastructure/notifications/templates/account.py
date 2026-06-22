"""Account namespace notification templates — Flow 2 §7 / T-038."""

from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final = frozenset({"en", "ur", "sd", "ps"})
DEFAULT_LOCALE: Final = "en"

# template_key -> variant -> locale -> {title, body, subject?}
ACCOUNT_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "account.invite_sent": {
        "default": {
            "en": {
                "subject": "You have been invited to IqbalAI",
                "title": "Invitation sent",
                "body": "{inviter_name} invited you to join IqbalAI. Accept within 7 days: {invite_url}",
            },
            "ur": {
                "subject": "آپ کو IqbalAI میں مدعو کیا گیا ہے",
                "title": "دعوت نامہ بھیجا گیا",
                "body": "{inviter_name} نے آپ کو IqbalAI میں شامل ہونے کی دعوت دی ہے۔ 7 دنوں میں قبول کریں: {invite_url}",
            },
            "sd": {
                "subject": "توهان کي IqbalAI ۾ دعوت ڏني وئي آهي",
                "title": "دعوت موڪلي وئي",
                "body": "{inviter_name} توهان کي IqbalAI ۾ شامل ٿيڻ لاءِ دعوت ڏني آهي۔ 7 ڏينهن اندر قبول ڪريو: {invite_url}",
            },
            "ps": {
                "subject": "تاسو IqbalAI ته بل شوي یاست",
                "title": "بل ولېږل شو",
                "body": "{inviter_name} تاسو IqbalAI ته د شاملېدو بل درکړی دی۔ په 7 ورځو کې ومنئ: {invite_url}",
            },
        }
    },
    "account.invite_expired": {
        "default": {
            "en": {
                "title": "Invitation expired",
                "body": "The invitation to {email} ({role}) expired without being accepted.",
            },
            "ur": {
                "title": "دعوت نامہ ختم ہو گیا",
                "body": "{email} ({role}) کی دعوت بغیر قبول کیے ختم ہو گئی۔",
            },
            "sd": {
                "title": "دعوت ختم ٿي وئي",
                "body": "{email} ({role}) جي دعوت قبول ڪرڻ کان سواءِ ختم ٿي وئي۔",
            },
            "ps": {
                "title": "بل پای ته ورسید",
                "body": "د {email} ({role}) بل پرته له منلو څخه پای ته ورسید۔",
            },
        }
    },
    "account.invite_accepted": {
        "default": {
            "en": {
                "title": "Invitation accepted",
                "body": "{name} ({email}) accepted your invitation as {role}.",
            },
            "ur": {
                "title": "دعوت نامہ قبول ہو گیا",
                "body": "{name} ({email}) نے {role} کے طور پر آپ کی دعوت قبول کر لی۔",
            },
            "sd": {
                "title": "دعوت قبول ٿي وئي",
                "body": "{name} ({email}) توهان جي دعوت {role} جي طور تي قبول ڪئي۔",
            },
            "ps": {
                "title": "بل ومنل شو",
                "body": "{name} ({email}) ستاسو بل د {role} په توګه ومنه۔",
            },
        }
    },
    "account.suspended": {
        "target": {
            "en": {
                "title": "Account suspended",
                "body": "Your IqbalAI account has been suspended. Contact your school administrator.",
            },
            "ur": {
                "title": "اکاؤنٹ معطل",
                "body": "آپ کا IqbalAI اکاؤنٹ معطل کر دیا گیا ہے۔ اپنے اسکول منتظم سے رابطہ کریں۔",
            },
            "sd": {
                "title": "اکاؤنٽ معطل",
                "body": "توهان جو IqbalAI اکاؤنٽ معطل ڪيو ويو آهي۔ پنهنجي اسڪول منتظم سان رابطو ڪريو۔",
            },
            "ps": {
                "title": "حساب ځنډول شو",
                "body": "ستاسو IqbalAI حساب ځنډول شوی دی۔ له خپل ښوونځي مدیر سره اړیکه ونیسئ۔",
            },
        },
        "actor": {
            "en": {
                "title": "User suspended",
                "body": "You suspended {email}'s account.",
            },
            "ur": {
                "title": "صارف معطل",
                "body": "آپ نے {email} کا اکاؤنٹ معطل کر دیا۔",
            },
            "sd": {
                "title": "استعمال ڪندڙ معطل",
                "body": "توهان {email} جو اکاؤنٽ معطل ڪيو۔",
            },
            "ps": {
                "title": "کارن ځنډول شو",
                "body": "تاسو د {email} حساب ځنډ کړ۔",
            },
        },
    },
    "account.reactivated": {
        "target": {
            "en": {
                "subject": "Your IqbalAI account is active again",
                "title": "Account reactivated",
                "body": "Your IqbalAI account has been reactivated. You can sign in again.",
            },
            "ur": {
                "subject": "آپ کا IqbalAI اکاؤنٹ دوبارہ فعال ہے",
                "title": "اکاؤنٹ بحال",
                "body": "آپ کا IqbalAI اکاؤنٹ دوبارہ فعال کر دیا گیا ہے۔ آپ دوبارہ سائن ان کر سکتے ہیں۔",
            },
            "sd": {
                "subject": "توهان جو IqbalAI اکاؤنٽ ٻيهر فعال آهي",
                "title": "اکاؤنٽ بحال",
                "body": "توهان جو IqbalAI اکاؤنٽ ٻيهر فعال ڪيو ويو آهي۔ توهان ٻيهر سائن ان ٿي سگهو ٿا۔",
            },
            "ps": {
                "subject": "ستاسو IqbalAI حساب بیا فعال دی",
                "title": "حساب بیا فعال شو",
                "body": "ستاسو IqbalAI حساب بیا فعال شوی دی۔ تاسو بیا ننوتلای شئ۔",
            },
        },
        "actor": {
            "en": {
                "subject": "User account reactivated",
                "title": "User reactivated",
                "body": "You reactivated {email}'s account.",
            },
            "ur": {
                "subject": "صارف کا اکاؤنٹ بحال",
                "title": "صارف بحال",
                "body": "آپ نے {email} کا اکاؤنٹ بحال کر دیا۔",
            },
            "sd": {
                "subject": "استعمال ڪندڙ جو اکاؤنٽ بحال",
                "title": "استعمال ڪندڙ بحال",
                "body": "توهان {email} جو اکاؤنٽ بحال ڪيو۔",
            },
            "ps": {
                "subject": "د کارن حساب بیا فعال شو",
                "title": "کارن بیا فعال شو",
                "body": "تاسو د {email} حساب بیا فعال کړ۔",
            },
        },
    },
    "account.deactivated": {
        "default": {
            "en": {
                "subject": "Your IqbalAI account has been deactivated",
                "title": "Account deactivated",
                "body": "Your IqbalAI account has been permanently deactivated.",
            },
            "ur": {
                "subject": "آپ کا IqbalAI اکاؤنٹ غیر فعال کر دیا گیا",
                "title": "اکاؤنٹ غیر فعال",
                "body": "آپ کا IqbalAI اکاؤنٹ مستقل طور پر غیر فعال کر دیا گیا ہے۔",
            },
            "sd": {
                "subject": "توهان جو IqbalAI اکاؤنٽ غير فعال ڪيو ويو",
                "title": "اکاؤنٽ غير فعال",
                "body": "توهان جو IqbalAI اکاؤنٽ مستقل طور غير فعال ڪيو ويو آهي۔",
            },
            "ps": {
                "subject": "ستاسو IqbalAI حساب غیرفعال شو",
                "title": "حساب غیرفعال شو",
                "body": "ستاسو IqbalAI حساب د تل لپاره غیرفعال شوی دی۔",
            },
        }
    },
    "account.bulk_import_done": {
        "default": {
            "en": {
                "title": "Bulk import validated",
                "body": "Dry-run complete: {success_rows} valid, {failed_rows} invalid out of {total_rows} rows.",
            },
            "ur": {
                "title": "بلک درآمد کی تصدیق",
                "body": "ڈry-run مکمل: {total_rows} میں سے {success_rows} درست، {failed_rows} غلط۔",
            },
            "sd": {
                "title": "بلڪ درآمد جي تصديق",
                "body": "Dry-run مڪمل: {total_rows} مان {success_rows} صحيح، {failed_rows} غلط۔",
            },
            "ps": {
                "title": "د ډله‌ای واردولو تصدیق",
                "body": "Dry-run بشپړ: له {total_rows} څخه {success_rows} سم، {failed_rows} ناسم۔",
            },
        }
    },
    "account.teacher_assigned_offering": {
        "default": {
            "en": {
                "title": "New grade-subject assignment",
                "body": "You have been assigned to teach {subject_name} for {grade_name}.",
            },
            "ur": {
                "title": "نیا گریڈ-مضمون تفویض",
                "body": "آپ کو {grade_name} کے لیے {subject_name} پڑھانے کے لیے مقرر کیا گیا ہے۔",
            },
            "sd": {
                "title": "نئون گريڊ-مضمون تفويض",
                "body": "توهان کي {grade_name} لاءِ {subject_name} پڙهائڻ لاءِ مقرر ڪيو ويو آهي۔",
            },
            "ps": {
                "title": "نوی درجه-مضمون ګمارل",
                "body": "تاسو د {grade_name} لپاره د {subject_name} تدریس لپاره ګمارل شوي یاست۔",
            },
        }
    },
    "account.capacity_changed": {
        "default": {
            "en": {
                "title": "Teaching capacity updated",
                "body": "{teacher_name} changed capacity from {old_capacity} to {new_capacity} ({assignment_count} current assignments).",
            },
            "ur": {
                "title": "تدریسی گنجائش اپ ڈیٹ",
                "body": "{teacher_name} نے گنجائش {old_capacity} سے {new_capacity} کر دی ({assignment_count} موجودہ تفویضات)۔",
            },
            "sd": {
                "title": "تدريسي گنجائش اپڊيٽ",
                "body": "{teacher_name} گنجائش {old_capacity} کان {new_capacity} ڪئي ({assignment_count} موجوده تفويضون)۔",
            },
            "ps": {
                "title": "د تدریس ظرفیت تازه شوه",
                "body": "{teacher_name} ظرفیت له {old_capacity} څخه {new_capacity} ته بدله کړه ({assignment_count} اوسنۍ ګمارنې)۔",
            },
        }
    },
    "account.capacity_override": {
        "default": {
            "en": {
                "title": "Teacher capacity override",
                "body": "{actor_name} overrode the capacity limit for {teacher_name} ({assignment_count}/{capacity}).",
            },
            "ur": {
                "title": "استاد کی گنجائش سے تجاوز",
                "body": "{actor_name} نے {teacher_name} کی گنجائش ({assignment_count}/{capacity}) سے تجاوز کیا۔",
            },
            "sd": {
                "title": "استاد جي گنجائش کان تجاوز",
                "body": "{actor_name} {teacher_name} جي گنجائش ({assignment_count}/{capacity}) کان تجاوز ڪيو۔",
            },
            "ps": {
                "title": "د ښوونکي ظرفیت له پوره تیری",
                "body": "{actor_name} د {teacher_name} ظرفیت ({assignment_count}/{capacity}) له پوره تیری وکړه۔",
            },
        }
    },
    "account.parent_welcome": {
        "default": {
            "en": {
                "subject": "Welcome to IqbalAI — parent account created",
                "title": "Parent account created",
                "body": "Hi {name}, your IqbalAI parent account is ready. Verify your email and sign in to link to your child's account.",
            },
            "ur": {
                "subject": "IqbalAI میں خوش آمدید — والدین کا اکاؤنٹ بن گیا",
                "title": "والدین کا اکاؤنٹ بن گیا",
                "body": "سلام {name}، آپ کا IqbalAI والدین اکاؤنٹ تیار ہے۔ اپنا ای میل تصدیق کریں اور اپنے بچے کے اکاؤنٹ سے لنک کرنے کے لیے سائن ان کریں۔",
            },
            "sd": {
                "subject": "IqbalAI ۾ ڀليڪار — والدين جو اڪائونٽ ٺهي ويو",
                "title": "والدين جو اڪائونٽ ٺهي ويو",
                "body": "سلام {name}، توهان جو IqbalAI والدين اڪائونٽ تيار آهي۔ پنهنجي اي ميل جي تصديق ڪريو ۽ پنهنجي ٻار جي اڪائونٽ سان لنڪ ڪرڻ لاءِ سائن ان ٿيو۔",
            },
            "ps": {
                "subject": "IqbalAI ته ښه راغلاست — د والدین حساب جوړ شو",
                "title": "د والدین حساب جوړ شو",
                "body": "سلام {name}، ستاسو IqbalAI والدین حساب چمتو دی۔ خپل بریښنالیک تایید کړئ او د خپل ماشوم حساب سره د نښلولو لپاره ننوځئ۔",
            },
        }
    },
    "account.parent_auto_suspended": {
        "default": {
            "en": {
                "subject": "IqbalAI parent account suspended",
                "title": "Parent account suspended",
                "body": "Hi {name}, your parent account was suspended after 90 days without linking to a student. Sign in again to resume and link to your child.",
            },
            "ur": {
                "subject": "IqbalAI والدین اکاؤنٹ معطل",
                "title": "والدین اکاؤنٹ معطل",
                "body": "سلام {name}، آپ کا والدین اکاؤنٹ 90 دن تک بچے سے لنک نہ ہونے کی وجہ سے معطل کر دیا گیا۔ دوبارہ سائن ان کریں تاکہ دوبارہ فعال ہو اور اپنے بچے سے لنک کریں۔",
            },
            "sd": {
                "subject": "IqbalAI والدين اڪائونٽ معطل",
                "title": "والدين اڪائونٽ معطل",
                "body": "سلام {name}، توهان جو والدين اڪائونٽ 90 ڏينهن تائين ٻار سان لنڪ نہ ٿيڻ سبب معطل ڪيو ويو۔ ٻيهر سائن ان ٿي واپس فعال ڪريو ۽ پنهنجي ٻار سان لنڪ ڪريو۔",
            },
            "ps": {
                "subject": "IqbalAI والدین حساب ځنډول شو",
                "title": "والدین حساب ځنډول شو",
                "body": "سلام {name}، ستاسو والدین حساب د 90 ورځو لپاره د زده کونکي سره د نښلولو پرته ځنډول شو۔ بیا ننوځئ ترڅو بیا فعال شي او خپل ماشوم سره ونښلوئ۔",
            },
        }
    },
}

TEMPLATE_CHANNELS: dict[str, frozenset[str]] = {
    "account.invite_sent": frozenset({"email"}),
    "account.invite_expired": frozenset({"in_app"}),
    "account.invite_accepted": frozenset({"in_app"}),
    "account.suspended": frozenset({"in_app"}),
    "account.reactivated": frozenset({"email", "in_app"}),
    "account.deactivated": frozenset({"email", "in_app"}),
    "account.bulk_import_done": frozenset({"in_app"}),
    "account.teacher_assigned_offering": frozenset({"in_app"}),
    "account.capacity_changed": frozenset({"in_app"}),
    "account.capacity_override": frozenset({"in_app"}),
    "account.parent_welcome": frozenset({"email"}),
    "account.parent_auto_suspended": frozenset({"email"}),
}


def render_account_template(
    template_key: str,
    *,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    params: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return rendered title/body/subject for a template key and locale."""
    if template_key not in ACCOUNT_TEMPLATES:
        raise KeyError(f"Unknown account template: {template_key}")

    variants = ACCOUNT_TEMPLATES[template_key]
    if variant not in variants:
        raise KeyError(f"Unknown variant '{variant}' for template '{template_key}'")

    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    fields = variants[variant].get(loc) or variants[variant][DEFAULT_LOCALE]
    safe_params = params or {}
    return {key: value.format(**safe_params) for key, value in fields.items()}
