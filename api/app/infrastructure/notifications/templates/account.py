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
    "account.export_ready": {
        "default": {
            "en": {
                "subject": "Your IqbalAI data export is ready",
                "title": "Data export ready",
                "body": "Hi {name}, your personal data export is ready to download. It will remain available for 7 days from your Data & Privacy page.",
            },
            "ur": {
                "subject": "آپ کا IqbalAI ڈیٹا ایکسپورٹ تیار ہے",
                "title": "ڈیٹا ایکسپورٹ تیار",
                "body": "سلام {name}، آپ کا ذاتی ڈیٹا ایکسپورٹ ڈاؤن لوڈ کے لیے تیار ہے۔ یہ 7 دنوں تک آپ کے ڈیٹا اور پرائیویسی صفحے سے دستیاب رہے گا۔",
            },
            "sd": {
                "subject": "توهان جو IqbalAI ڊيٽا برآمد تيار آهي",
                "title": "ڊيٽا برآمد تيار",
                "body": "سلام {name}، توهان جو ذاتي ڊيٽا برآمد ڊائون لوڊ لاءِ تيار آهي۔ اهو 7 ڏينهن تائين توهان جي ڊيٽا ۽ پرائیویسي صفحي تان دستياب رهندو۔",
            },
            "ps": {
                "subject": "ستاسو IqbalAI ډیټا صادرات چمتو دی",
                "title": "ډیټا صادرات چمتو",
                "body": "سلام {name}، ستاسو شخصي ډیټا صادرات د ډاونلوډ لپاره چمتو دی۔ دا به د 7 ورځو لپاره ستاسو د ډیټا او محرمیت پاڼې څخه شتون ولري۔",
            },
        }
    },
    "account.deletion_grace_started": {
        "default": {
            "en": {
                "subject": "IqbalAI account deletion request received",
                "title": "Deletion request queued",
                "body": "Hi {name}, we received your account deletion request. It enters a 30-day grace period (scheduled review on {scheduled_date}). You may cancel anytime before then. We do not hard-delete immediately due to legal audit retention.",
            },
            "ur": {
                "subject": "IqbalAI اکاؤنٹ حذف کی درخواست موصول",
                "title": "حذف کی درخواست قطار میں",
                "body": "سلام {name}، ہمیں آپ کی اکاؤنٹ حذف کی درخواست موصول ہوئی۔ 30 دن کی مہلت شروع ہو گئی (جائزہ {scheduled_date} کو)۔ آپ اس سے پہلے کسی بھی وقت منسوخ کر سکتے ہیں۔ قانونی آڈٹ برقراری کی وجہ سے فوری hard-delete نہیں ہوتا۔",
            },
            "sd": {
                "subject": "IqbalAI اڪائونٽ حذف جي درخواست موصول",
                "title": "حذف جي درخواست قطار ۾",
                "body": "سلام {name}، اسان کي توهان جي اڪائونٽ حذف جي درخواست موصول ٿي۔ 30 ڏينهن جي مهلت شروع ٿي ({scheduled_date} تي جائزو)۔ توهان ان کان اڳ ڪنهن به وقت منسوخ ڪري سگهو ٿا۔ قانوني آڊٽ برقرار رکڻ سبب فوري hard-delete نه ٿيندو۔",
            },
            "ps": {
                "subject": "د IqbalAI حساب د حذف غوښتنه ترلاسه شوه",
                "title": "د حذف غوښتنه په قطار کې",
                "body": "سلام {name}، موږ ستاسو د حساب د حذف غوښتنه ترلاسه کړه۔ 30 ورځې مهلت پیل شو (کتنه {scheduled_date})۔ تاسو کولی شئ مخکې له دې هر وخت لغوه کړئ۔ د قانوني آډیټ ساتنې له امله سمدستي hard-delete نه کیږي۔",
            },
        }
    },
    "account.student_invited": {
        "default": {
            "en": {
                "subject": "You are invited to IqbalAI",
                "title": "School enrollment invite",
                "body": "Hi {name}, you have been enrolled at {school_name}. Accept your invite within 7 days: {invite_url}",
            },
            "ur": {
                "subject": "آپ کو IqbalAI میں مدعو کیا گیا",
                "title": "اسکول میں داخلہ دعوت",
                "body": "سلام {name}، آپ {school_name} میں داخل ہوئے۔ 7 دنوں میں دعوت قبول کریں: {invite_url}",
            },
            "sd": {
                "subject": "توهان کي IqbalAI ۾ دعوت",
                "title": "اسڪول داخلہ دعوت",
                "body": "سلام {name}، توهان {school_name} ۾ داخل ٿيا۔ 7 ڏينهن ۾ دعوت قبول ڪريو: {invite_url}",
            },
            "ps": {
                "subject": "تاسو IqbalAI ته بل شوي",
                "title": "د ښوونځي ننوتل",
                "body": "سلام {name}، تاسو {school_name} کې شامل شوي۔ په 7 ورځو کې بل ومنئ: {invite_url}",
            },
        }
    },
    "account.graduated": {
        "default": {
            "en": {
                "subject": "Congratulations — you've graduated!",
                "title": "Graduation confirmed",
                "body": "Hi {name}, you've graduated! For 6 months you can still use Self-Study in your school account. After that, your account moves to Independent mode with the same login.",
            },
            "ur": {
                "subject": "مبارک ہو — آپ گریجویشن کر چکے ہیں!",
                "title": "گریجویشن کی تصدیق",
                "body": "سلام {name}، آپ گریجویٹ ہو گئے! 6 ماہ تک Self-Study اسکول اکاؤنٹ میں استعمال کر سکتے ہیں۔ اس کے بعد Independent موڈ میں منتقل ہوں گے — وہی لاگ ان۔",
            },
            "sd": {
                "subject": "مبارڪون — توهان گريجوئيشن ڪري چuka!",
                "title": "گريجوئيشن جي تصديق",
                "body": "سلام {name}، توهان گريجوئيٽ ٿي ويا! 6 مهina Self-Study اسڪول اڪائونٽ ۾ استعمال ڪري سگهو ٿا۔ پوءِ Independent موڊ ۾ منتقل — ساڳيو لاگ ان۔",
            },
            "ps": {
                "subject": "مبارک شه — تاسو فارغ شوي!",
                "title": "د فارغتیا تایید",
                "body": "سلام {name}، تاسو فارغ شوي! د 6 میاشتو لپاره Self-Study په ښوونځي حساب کې کارولی شئ۔ وروسته Independent حالت ته — ورته ننوتل۔",
            },
        }
    },
    "account.migration_reminder_30": {
        "default": {
            "en": {
                "subject": "IqbalAI account migration in 30 days",
                "title": "Migration reminder (30 days)",
                "body": "Hi {name}, your school account moves to Independent mode on {migration_date} ({days_remaining} days). Export your data from Data & Privacy if needed.",
            },
            "ur": {
                "subject": "30 دن میں اکاؤنٹ منتقلی",
                "title": "منتقلی یاد دہانی",
                "body": "سلام {name}، {migration_date} کو Independent موڈ ({days_remaining} دن)۔ ضرورت ہو تو ڈیٹا ایکسپورٹ کریں۔",
            },
            "sd": {
                "subject": "30 ڏينهن ۾ منتقلي",
                "title": "منتقلي ياد",
                "body": "سلام {name}، {migration_date} تي Independent ({days_remaining} ڏينهن)۔ ضرورت هجي ته ڊيٽا برآمد ڪريو۔",
            },
            "ps": {
                "subject": "په 30 ورځو کې انتقال",
                "title": "د انتقال یادونه",
                "body": "سلام {name}، {migration_date} Independent ({days_remaining} ورځې)۔ اړتیا وي ډیټا صادر کړئ۔",
            },
        }
    },
    "account.migration_reminder_7": {
        "default": {
            "en": {
                "subject": "IqbalAI account migration in 7 days",
                "title": "Migration reminder (7 days)",
                "body": "Hi {name}, your account moves to Independent mode on {migration_date}. Parent links will be removed. Export data now if you need a copy.",
            },
            "ur": {
                "subject": "7 دن میں منتقلی",
                "title": "منتقلی یاد دہانی",
                "body": "سلام {name}، {migration_date} کو Independent۔ والدین لنک ختم۔ ابھی ڈیٹا ایکسپورٹ کریں۔",
            },
            "sd": {
                "subject": "7 ڏينهن ۾ منتقلي",
                "title": "منتقلي ياد",
                "body": "سلام {name}، {migration_date} Independent۔ والدين لنڪ ختم۔ هاڻي ڊيٽا برآمد ڪريو۔",
            },
            "ps": {
                "subject": "په 7 ورځو کې انتقال",
                "title": "د انتقال یادونه",
                "body": "سلام {name}، {migration_date} Independent۔ د والدین اړیکې لرې۔ اوس ډیټا صادر کړئ۔",
            },
        }
    },
    "account.migration_complete": {
        "default": {
            "en": {
                "subject": "Your IqbalAI account has moved to Independent mode",
                "title": "Migration complete",
                "body": "Hi {name}, your account has moved to Independent mode. Sign in with the same email and password — Self-Study continues; school Lecture mode is no longer available.",
            },
            "ur": {
                "subject": "آپ کا اکاؤنٹ Independent موڈ میں",
                "title": "منتقلی مکمل",
                "body": "سلام {name}، Independent موڈ — وہی ای میل/پاس ورڈ۔ Self-Study جاری؛ Lecture نہیں۔",
            },
            "sd": {
                "subject": "توهان جو اڪائونٽ Independent",
                "title": "منتقلي مڪمل",
                "body": "سلام {name}، Independent — ساڳي اي ميل/پاسورڊ۔ Self-Study جاري؛ Lecture نه۔",
            },
            "ps": {
                "subject": "ستاسو حساب Independent شو",
                "title": "انتقال بشپړ",
                "body": "سلام {name}، Independent — ورته بریښنالیک/پټنوم۔ Self-Study دوام لري؛ Lecture نشته۔",
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
    "account.export_ready": frozenset({"email", "in_app"}),
    "account.deletion_grace_started": frozenset({"email", "in_app"}),
    "account.student_invited": frozenset({"email", "in_app"}),
    "account.graduated": frozenset({"email", "in_app"}),
    "account.migration_reminder_30": frozenset({"email", "in_app"}),
    "account.migration_reminder_7": frozenset({"email", "in_app"}),
    "account.migration_complete": frozenset({"email", "in_app"}),
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
