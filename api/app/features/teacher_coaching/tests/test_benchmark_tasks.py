"""T-139 — `benchmark.update_weekly` Celery beat task (ARCH §10.6)."""

from __future__ import annotations

from unittest.mock import patch

from app.features.teacher_coaching.benchmark_tasks import update_weekly


def test_update_weekly_delegates_to_run_db() -> None:
    with patch(
        "app.features.teacher_coaching.benchmark_tasks.run_db",
        return_value={"cohorts_computed": 2, "teachers_updated": 6},
    ) as mock_run_db:
        result = update_weekly.run()

    assert result == {"cohorts_computed": 2, "teachers_updated": 6}
    mock_run_db.assert_called_once()
