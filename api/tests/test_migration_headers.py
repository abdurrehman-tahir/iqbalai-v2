"""§4.12 migration header lint (T-234)."""

from __future__ import annotations

from pathlib import Path

SCHOOL_MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "school"


def test_all_school_migrations_have_section_4_12_headers() -> None:
    missing: list[str] = []
    for path in sorted(SCHOOL_MIGRATIONS.glob("*.py")):
        text = path.read_text()
        for field in ("Purpose:", "Risk:", "Reversible:"):
            if field not in text:
                missing.append(f"{path.name}: missing {field}")
    assert missing == [], "\n".join(missing)
