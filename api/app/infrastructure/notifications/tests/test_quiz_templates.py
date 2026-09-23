"""Quiz notification template tests (T-149)."""

from __future__ import annotations

from app.infrastructure.notifications.templates.lectures import render_lecture_template
from app.infrastructure.notifications.templates.quiz import QUIZ_TEMPLATES, render_quiz_template


def test_quiz_templates_cover_four_locales_no_todo() -> None:
    for key, variants in QUIZ_TEMPLATES.items():
        for variant, locales in variants.items():
            for loc in ("en", "ur", "sd", "ps"):
                assert loc in locales, f"{key}/{variant} missing {loc}"
                for field in ("title", "body"):
                    assert "__TODO__" not in locales[loc][field]


def test_render_quiz_available() -> None:
    rendered = render_quiz_template("quiz.available", locale="en", params={"topic": "Forces"})
    assert "Forces" in rendered["body"]


def test_lecture_published_student_and_parent_variants() -> None:
    student = render_lecture_template(
        "lectures.published", locale="en", variant="student", params={"topic": "Optics"}
    )
    parent = render_lecture_template(
        "lectures.published", locale="ur", variant="parent", params={"topic": "Optics"}
    )
    assert "Optics" in student["body"]
    assert parent["title"]
    assert "__TODO__" not in parent["body"]
