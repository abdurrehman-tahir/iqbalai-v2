"""Shared fixtures for cross-feature tests in ``tests/``.

``pg`` is the M-15 real-Postgres fixture (skips when DB_URL is unset).
"""

from app.features.student_highlights.tests.pg_support import pg

__all__ = ["pg"]
