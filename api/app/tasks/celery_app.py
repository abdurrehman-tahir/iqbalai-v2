"""Celery worker entrypoint — configures broker and registers tasks."""

import app.tasks.smoke  # noqa: F401
from app.infrastructure.celery.celery_app import celery_app

# Ingestion tasks pull optional PDF/langchain deps — register when available.
try:
    import app.features.library.school_tasks  # noqa: F401
except ImportError:
    pass

try:
    import app.features.library.tasks  # noqa: F401
except ImportError:
    pass

try:
    import app.features.invites.tasks  # noqa: F401
except ImportError:
    pass

try:
    import app.features.parent_signup.tasks  # noqa: F401
except ImportError:
    pass

try:
    import app.features.student_onboarding.tasks  # noqa: F401
except ImportError:
    pass

try:
    import app.features.data_rights.tasks  # noqa: F401
except ImportError:
    pass

__all__ = ["celery_app"]
