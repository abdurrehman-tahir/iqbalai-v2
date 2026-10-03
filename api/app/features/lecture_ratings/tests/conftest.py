"""Expose the M-15 real-Postgres fixture to lecture_ratings tests."""

from app.features.student_highlights.tests.pg_support import pg

__all__ = ["pg"]
