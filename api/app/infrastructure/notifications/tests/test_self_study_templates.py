from app.infrastructure.notifications.templates.self_study import (
    TEMPLATE_CHANNELS,
    render_self_study_template,
)


def test_render_exam_countdown_template() -> None:
    rendered = render_self_study_template(
        "self_study.exam_countdown",
        params={"days_remaining": "30", "exam_date": "2026-12-01"},
    )
    assert "30" in rendered["body"]
    assert "2026-12-01" in rendered["body"]


def test_render_exam_passed_all_locales() -> None:
    for locale in ("en", "ur", "sd", "ps"):
        rendered = render_self_study_template(
            "self_study.exam_passed",
            locale=locale,
            params={"exam_date": "2026-01-01"},
        )
        assert rendered["title"]
        assert "2026-01-01" in rendered["body"]
    assert "self_study.exam_passed" in TEMPLATE_CHANNELS
