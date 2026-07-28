"""T-105 — focus area derivation never emits grades/scores."""

from __future__ import annotations

from app.features.diagnostics.focus_areas import derive_focus_areas
from app.features.diagnostics.schemas import DiagnosticQuestion


def test_derive_focus_areas_skips_answered_topics() -> None:
    questions = [
        DiagnosticQuestion(id="q1", prompt="a", choices=["x"], topic="Optics"),
        DiagnosticQuestion(id="q2", prompt="b", choices=[], topic="Friction"),
    ]
    areas, summary = derive_focus_areas(questions=questions, answers={"q1": "x"})
    assert len(areas) == 1
    assert areas[0].topic == "Friction"
    assert "%" not in areas[0].suggestion
    assert "coaching" in summary.lower() or "guidance" in summary.lower()


def test_derive_focus_areas_all_answered_still_coaches() -> None:
    questions = [DiagnosticQuestion(id="q1", prompt="a", topic="Optics")]
    areas, summary = derive_focus_areas(questions=questions, answers={"q1": "ok"})
    assert len(areas) == 1
    assert areas[0].topic == "Optics"
    assert "practicing" in areas[0].suggestion.lower()
    assert "coaching" in summary.lower() or "guidance" in summary.lower()
