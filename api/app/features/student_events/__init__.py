"""student_events feature package — Analytics Consumer destination (T-174)."""

from app.features.student_events.models import (
    IndependentStudentEvent,
    SchoolStudentEvent,
    StudentEvent,
    StudentEventTenantType,
)

__all__ = [
    "IndependentStudentEvent",
    "SchoolStudentEvent",
    "StudentEvent",
    "StudentEventTenantType",
]
