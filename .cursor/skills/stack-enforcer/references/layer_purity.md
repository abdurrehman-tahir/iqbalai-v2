# Layer purity matrix — detailed

Per `docs/ARCHITECTURE.md` §2.4 and §2.5.

## The dependency direction

Inside a feature folder (`app/features/<feature>/`):

```
                  ┌──────────────┐
                  │  router.py   │  (thin: parse → call service → format response)
                  └──────┬───────┘
                         │ calls
                         ▼
                  ┌──────────────┐
                  │  service.py  │  (business logic; orchestrates)
                  └──────┬───────┘
                         │ calls
                         ▼
                  ┌──────────────┐
                  │repository.py │  (data access; SQLAlchemy lives here)
                  └──────┬───────┘
                         │ reads/writes
                         ▼
                  ┌──────────────┐
                  │  models.py   │  (ORM definitions)
                  └──────────────┘
```

Cross-feature:
- `service A` MAY call `service B`
- `service A` MAY NOT call `repository B` directly
- `router A` MAY NOT call anything from feature B

## Per-file rules

### `router.py`

**Allowed imports:**
- `from fastapi import APIRouter, Depends, Header, ...`
- `from .service import <Service class or get_<service> dependency>`
- `from .schemas import <Schemas>`
- `from .dependencies import <feature-local FastAPI deps>` (if any)
- `from app.core.dependencies import require_role, require_scope, ...`
- `from app.core.responses import ...` (envelope helpers)
- `from app.features.<feature>.models import <Enum>` (Postgres enum types passed in URL params — narrow exception)

**Forbidden imports:**
- `from sqlalchemy import ...` — routers must not touch SQLAlchemy
- `from .repository import ...` — services own the repository, routers don't
- `from .models import <ORM model class>` (other than enums) — don't leak ORM models to HTTP layer
- `from fastapi import HTTPException` — use the custom exception classes from `app/core/exceptions.py` instead
- `from app.features.<other>.router import ...` — never call another feature's router
- `from app.infrastructure.*` directly — services orchestrate infrastructure, not routers

**Pattern that's correct:**

```python
# api/app/features/lectures/router.py
from fastapi import APIRouter, Depends, Header
from uuid import UUID

from app.core.dependencies import require_role, idempotency_required
from app.features.users.models import UserRole
from .schemas import LectureCreate, LectureRead
from .service import LectureService, get_lecture_service

router = APIRouter(prefix="/lectures", tags=["lectures"])


@router.post("", response_model=LectureRead, status_code=201, operation_id="lectures_create")
async def create_lecture(
    payload: LectureCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user = Depends(require_role(UserRole.TEACHER)),
    service: LectureService = Depends(get_lecture_service),
    _: None = Depends(idempotency_required),
):
    return await service.create(payload, user=user)
```

### `service.py`

**Allowed imports:**
- `from .repository import <Repository class or get_<repo> dep>`
- `from .schemas import <Schemas>`
- `from app.core.exceptions import NotFoundError, PermissionDeniedError, ...`
- `from app.infrastructure.<llm|rag|voice|storage|cache|events|...> import ...`
- `from app.features.<other-feature>.service import ...` — cross-feature via services is allowed
- `from app.features.users.models import UserRole` — enums

**Forbidden imports:**
- `from sqlalchemy import ...` — repository handles the ORM
- `from fastapi import Request, Response, HTTPException, ...` — service should be HTTP-agnostic
- `from .models import <ORM model>` — repository returns schemas, not ORM models
- `from app.features.<other>.repository import ...` — repositories are private to their feature
- `from app.features.<other>.router import ...` — never

**Pattern that's correct:**

```python
# api/app/features/lectures/service.py
from uuid import UUID
from app.core.exceptions import NotFoundError
from app.infrastructure.events import event_publisher
from app.infrastructure.events.schemas import LecturePublishedV1
from app.features.users.service import UserService
from .repository import LectureRepository
from .schemas import LectureCreate, LectureRead


class LectureService:
    def __init__(self, repo: LectureRepository, users: UserService):
        self.repo = repo
        self.users = users

    async def create(self, payload: LectureCreate, user) -> LectureRead:
        lecture = await self.repo.insert(payload, owner=user)
        await event_publisher.publish(
            "lecture.created",
            LecturePublishedV1(lecture_id=lecture.id, ...),
            actor=user,
        )
        return lecture
```

### `repository.py`

**Allowed imports:**
- `from sqlalchemy import select, update, delete, and_, or_`
- `from sqlalchemy.ext.asyncio import AsyncSession`
- `from .models import <ORM models>`
- `from .schemas import <Read/Update schemas>` — to return Pydantic schemas
- `from app.db.session import get_db_session` — session dep

**Forbidden imports:**
- `from .service import ...` — never (would be circular)
- `from .router import ...` — never
- `from app.features.<other>.repository import ...` — repositories don't cross-talk
- `from fastapi import ...` — repository is HTTP-agnostic
- `from app.infrastructure.events import ...` — events are a service-layer concern

**Pattern that's correct:**

```python
# api/app/features/lectures/repository.py
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Lecture, LectureLink
from .schemas import LectureRead


class LectureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, lecture_id: UUID, user) -> LectureRead | None:
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        # ... within-school filtering based on user.role
        result = await self.session.scalar(stmt)
        return LectureRead.model_validate(result) if result else None
```

### `models.py`

**Allowed imports:**
- SQLAlchemy types and decorators
- `from app.db.base import Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin`
- `from enum import StrEnum` — for Postgres native enum types
- `from uuid import UUID; from datetime import datetime` — type annotations

**Forbidden imports:**
- `from .schemas import ...` — models don't know about Pydantic
- `from .service import ...` — never
- `from .router import ...` — never
- Anything that triggers business logic

**Pattern that's correct:**

```python
# api/app/features/lectures/models.py
from datetime import datetime
from enum import StrEnum
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin


class TeachingMode(StrEnum):
    LECTURE = "lecture"
    SOCRATIC = "socratic"
    STORY = "story"
    APPLIED = "applied"


class Lecture(Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "lectures"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    teacher_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    teaching_mode: Mapped[TeachingMode] = mapped_column(...)
    # ...
```

### `schemas.py`

**Allowed imports:**
- `from pydantic import BaseModel, Field, ConfigDict`
- `from uuid import UUID; from datetime import datetime; from typing import ...`
- `from .models import <Enum classes only>` — for shared enum types between ORM and schemas

**Forbidden imports:**
- `from .models import <ORM model class>` — schemas are not ORM
- `from .service import ...` — schemas are data, not logic
- `from .router import ...` — never
- SQLAlchemy types

### `tasks.py`

**Allowed imports:**
- `from app.tasks.celery_app import celery_app`
- `from app.tasks.base import tenant_task`
- `from .service import <Service class or factory>`
- Standard types (`UUID`, `datetime`, primitives)
- `from app.infrastructure.events import event_publisher` — to publish follow-up events

**Forbidden imports:**
- `from .router import ...` — never
- `from .repository import ...` directly — go through service
- `from sqlalchemy import ...` — tasks don't manage DB directly
- `from fastapi import ...` — Celery is HTTP-agnostic

**Pattern that's correct:**

```python
# api/app/features/curricula/tasks.py
from uuid import UUID
from app.tasks.celery_app import celery_app
from app.tasks.base import tenant_task
from .service import get_curricula_service


@tenant_task(
    queue="ingestion",
    name="curricula.ingest",
    soft_time_limit=540,
    time_limit=600,
    autoretry_for=(...),
    max_retries=3,
)
async def ingest_curriculum(curriculum_id: UUID, school_id: UUID) -> None:
    service = get_curricula_service()
    await service.run_ingestion_pipeline(curriculum_id)
```

### `events.py`

**Allowed imports:**
- `from app.infrastructure.events import EventConsumer, EventEnvelope`
- `from app.infrastructure.events.schemas import <PayloadSchema>`
- `from .service import <Service>`
- `from app.infrastructure.events.dedup import deduped` — for idempotency

**Forbidden imports:**
- `from .router import ...` — never
- `from .repository import ...` directly — go through service
- `from sqlalchemy import ...` — same reason

## Detection patterns for common violations

| Pattern in router.py | Why it's wrong |
|---|---|
| `from sqlalchemy import select` | Routers don't touch the ORM |
| `session.scalar(stmt)` | The session is a repository concern |
| `Lecture(...)` (ORM model construction) | Schemas or repositories build these, never routers |
| `if lecture.deleted_at: ...` (business condition) | Business logic belongs in service |
| `raise HTTPException(...)` | Use custom exceptions from `app/core/exceptions.py` |

| Pattern in service.py | Why it's wrong |
|---|---|
| `from sqlalchemy import ...` | Services don't construct SQL — repository does |
| `from fastapi import Request` | Service should be HTTP-agnostic |
| `request.headers.get(...)` | Service receives parsed values, not raw HTTP |
| `from app.features.X.repository import ...` (X ≠ current feature) | Cross-feature data goes through services |

| Pattern in repository.py | Why it's wrong |
|---|---|
| `from .service import ...` | Would be circular |
| `await event_publisher.publish(...)` | Events are a service concern |
| `if user.role == "admin" and ...` (complex business logic) | Move to service; repository scopes data, services apply logic |

## When in doubt

If you're unsure where something belongs:

- **Touches HTTP request/response?** → router
- **Decides what data is allowed for this user?** → service (with help from `require_*` deps at the router)
- **Builds the SQL query?** → repository
- **Defines the table?** → models
- **Defines the input/output shape?** → schemas
- **Reacts to a cross-feature event?** → events
- **Runs in the background after a user action?** → tasks
- **Is shared with many features?** → `core/` (cross-cutting) or `infrastructure/` (external-system wrapper)
