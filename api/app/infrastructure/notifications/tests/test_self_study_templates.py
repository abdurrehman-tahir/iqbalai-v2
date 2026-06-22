from app.infrastructure.notifications.templates.self_study import render_self_study_template


def test_render_exam_countdown_template() -> None:
    rendered = render_self_study_template(
        "self_study.exam_countdown",
        params={"days_remaining": "30", "exam_date": "2026-12-01"},
    )
    assert "30" in rendered["body"]
    assert "2026-12-01" in rendered["body"]
