"""Unit tests for connections notification templates — T-081."""

from __future__ import annotations

from app.infrastructure.notifications.templates.connections import render_connections_template


def test_render_parent_link_pending_en() -> None:
    rendered = render_connections_template(
        "connections.parent_link_pending",
        params={"parent_name": "Parent One"},
    )
    assert "Parent One" in rendered["body"]
    assert rendered["title"] == "Parent link request"


def test_render_parent_link_approved_en() -> None:
    rendered = render_connections_template(
        "connections.parent_link_approved",
        params={"student_name": "Student One"},
    )
    assert "Student One" in rendered["body"]
