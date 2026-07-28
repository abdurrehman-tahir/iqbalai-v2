"""Unit tests for qualitative DNA confidence mapping — T-106."""

from __future__ import annotations

from app.features.diagnostics.dna_seed import build_topic_confidence, focus_areas_to_jsonb
from app.features.diagnostics.schemas import DiagnosticQuestion, FocusAreaRead


def test_build_topic_confidence_qualitative_only() -> None:
    questions = [
        DiagnosticQuestion(id="q1", prompt="a", topic="Optics"),
        DiagnosticQuestion(id="q2", prompt="b", topic="Friction"),
    ]
    conf = build_topic_confidence(questions=questions, answers={"q1": "x"})
    assert conf["Optics"] == {"level": "building", "answered": True}
    assert conf["Friction"] == {"level": "needs_focus", "answered": False}
    blob = str(conf)
    assert "%" not in blob
    assert "score" not in blob.lower()
    assert "grade" not in blob.lower()


def test_focus_areas_to_jsonb() -> None:
    areas = [FocusAreaRead(topic="Optics", suggestion="Spend more time on Optics.")]
    assert focus_areas_to_jsonb(areas) == [
        {"topic": "Optics", "suggestion": "Spend more time on Optics."}
    ]
