"""Expose the M-15 real-Postgres fixture to this package's tests."""

from app.features.student_highlights.tests.pg_support import pg

__all__ = ["pg"]
