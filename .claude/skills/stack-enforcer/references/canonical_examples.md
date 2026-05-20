# Canonical correct shapes

Copy-paste-able templates. Adapt the names; keep the structure.

## A complete minimal feature

Five files. This is what a new feature looks like.

### `api/app/features/example/models.py`

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin


class ExampleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Example(Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "examples"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[ExampleStatus] = mapped_column(
        # NOTE: also create the postgres enum in the Alembic migration
        nullable=False,
        default=ExampleStatus.DRAFT,
    )
```

### `api/app/features/example/schemas.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import ExampleStatus


class ExampleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class ExampleUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    status: ExampleStatus | None = None


class ExampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    owner_id: UUID
    status: ExampleStatus
    created_at: datetime
    updated_at: datetime
```

### `api/app/features/example/repository.py`

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import UserRole
from .models import Example
from .schemas import ExampleCreate, ExampleRead


class ExampleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, example_id: UUID, user) -> ExampleRead | None:
        stmt = select(Example).where(
            Example.id == example_id,
            Example.deleted_at.is_(None),
        )
        # Within-school narrowing for non-admins
        if user.role not in {UserRole.SCHOOL_ADMIN, UserRole.DISTRICT_ADMIN, UserRole.PLATFORM_ADMIN}:
            stmt = stmt.where(Example.owner_id == user.id)
        result = await self.session.scalar(stmt)
        return ExampleRead.model_validate(result) if result else None

    async def insert(self, payload: ExampleCreate, user) -> ExampleRead:
        obj = Example(
            title=payload.title,
            owner_id=user.id,
            school_id=user.school_id,
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return ExampleRead.model_validate(obj)
```

### `api/app/features/example/service.py`

```python
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.events import event_publisher
from .repository import ExampleRepository
from .schemas import ExampleCreate, ExampleRead


class ExampleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ExampleRepository(session)

    async def get(self, example_id: UUID, user) -> ExampleRead:
        result = await self.repo.get(example_id, user=user)
        if result is None:
            raise NotFoundError("example", example_id)
        return result

    async def create(self, payload: ExampleCreate, user) -> ExampleRead:
        async with self.session.begin():
            result = await self.repo.insert(payload, user=user)
        # After commit
        await event_publisher.publish(
            "example.created",
            ExampleCreatedV1(example_id=result.id),
            actor=user,
        )
        return result


# FastAPI dependency factory
async def get_example_service(session = Depends(get_db_session)) -> ExampleService:
    return ExampleService(session)
```

### `api/app/features/example/router.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.core.dependencies import require_role, idempotency_required
from app.features.users.models import UserRole
from .schemas import ExampleCreate, ExampleRead
from .service import ExampleService, get_example_service


router = APIRouter(prefix="/examples", tags=["examples"])


@router.post(
    "",
    response_model=ExampleRead,
    status_code=201,
    operation_id="examples_create",
    summary="Create an example",
)
async def create_example(
    payload: ExampleCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user = Depends(require_role(UserRole.TEACHER, UserRole.PLATFORM_ADMIN)),
    service: ExampleService = Depends(get_example_service),
    _: None = Depends(idempotency_required),
):
    return await service.create(payload, user=user)


@router.get(
    "/{example_id}",
    response_model=ExampleRead,
    operation_id="examples_get",
)
async def get_example(
    example_id: UUID,
    user = Depends(require_role(
        UserRole.TEACHER, UserRole.STUDENT, UserRole.SCHOOL_ADMIN,
        UserRole.DISTRICT_ADMIN, UserRole.PLATFORM_ADMIN, UserRole.COORDINATOR,
    )),
    service: ExampleService = Depends(get_example_service),
):
    return await service.get(example_id, user=user)
```

## A Celery task with full template

```python
# api/app/features/example/tasks.py
from uuid import UUID

from app.tasks.celery_app import celery_app
from app.tasks.base import tenant_task
from .service import get_example_service_for_task


@tenant_task(
    queue="default",
    name="example.do_thing",
    soft_time_limit=25,
    time_limit=30,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
async def do_thing(example_id: UUID, school_id: UUID) -> None:
    """Do the thing.

    Idempotency: natural — sets a deterministic value derived from example_id.
    """
    service = get_example_service_for_task(school_id=school_id)
    await service.do_thing(example_id)
```

## A NATS event handler

```python
# api/app/features/example/events.py
from app.infrastructure.events import EventConsumer, EventEnvelope
from app.infrastructure.events.dedup import deduped
from app.infrastructure.events.schemas import StudentQAAnsweredV1
from .service import get_example_service_for_consumer


consumer = EventConsumer(
    name="example-qa-aggregator",
    subjects=["student.qa.answered"],
)


@consumer.handler("student.qa.answered")
async def on_qa_answered(envelope: EventEnvelope, payload: StudentQAAnsweredV1) -> None:
    if await deduped(envelope.event_id, "example-qa-aggregator"):
        return
    service = get_example_service_for_consumer(school_id=envelope.tenant_id)
    await service.update_stats(student_id=payload.student_id)
```

## Publishing an event (inside a service)

```python
async def publish_example(self, example_id: UUID, user) -> ExampleRead:
    async with self.session.begin():
        result = await self.repo.publish(example_id, user=user)
        # session.commit() happens here when the context manager exits
    # AFTER commit:
    await event_publisher.publish(
        "example.published",
        ExamplePublishedV1(example_id=result.id, owner_id=result.owner_id),
        actor=user,
    )
    return result
```

## An LLM call (one-shot, structured output)

```python
# inside a service
from app.infrastructure.llm import llm_client
from app.infrastructure.llm.prompts import example_summary
from .schemas import ExampleSummaryOutput


async def summarize(self, example_id: UUID, user) -> ExampleSummaryOutput:
    example = await self.repo.get(example_id, user=user)
    if example is None:
        raise NotFoundError("example", example_id)

    result: ExampleSummaryOutput = await llm_client.generate(
        prompt=example_summary.render(
            example_summary.ExampleSummaryInput(text=example.body),
        ),
        task="extraction",
        response_model=ExampleSummaryOutput,
    )
    return result
```

## A streaming LLM call

```python
async def stream_qa(self, question: str, user):
    async for chunk in llm_client.stream(
        prompt=student_qa.render(...),
        task="student_qa",
    ):
        if chunk.kind == "token":
            yield chunk.text
        elif chunk.kind == "source":
            yield {"event": "source", "data": chunk.citation}
        elif chunk.kind == "done":
            return
```

## A RAG retrieval call (Pattern S)

```python
from app.infrastructure.rag import retriever, reranker
from app.infrastructure.rag.context import assemble_context


async def answer(self, query: str, user):
    # 1. Embed query (handled inside retriever)
    # 2. Hybrid retrieve (tenant-scoped automatically via build_tenant_filter)
    candidates = await retriever.search(
        collection="curriculum_chunks",
        query_text=query,
        user=user,                  # REQUIRED — tenant scope chokepoint
        top_k=50,
        extra_filter={"topic_ids": ["..."]},
    )
    # 3. Rerank
    top = await reranker.rerank(query, candidates, top_n=5)
    # 4. Assemble context
    context = assemble_context(top, budget_tokens=2500)
    # 5. Call LLM
    return await llm_client.generate(
        prompt=student_qa.render(StudentQAInput(question=query, context=context)),
        task="student_qa",
    )
```

## An Alembic migration with the locked header

```python
"""add example status column

Revision ID: 20260612_1430_abc123
Revises: 20260611_0915_xyz789
Create Date: 2026-06-12 14:30:00.000000

Purpose: add a `status` enum column to examples for publish/archive lifecycle
Risk: low (additive, with default)
Reversible: yes
"""
from alembic import op
import sqlalchemy as sa


revision = "20260612_1430_abc123"
down_revision = "20260611_0915_xyz789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    example_status = sa.Enum("draft", "published", "archived", name="example_status_enum")
    example_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "examples",
        sa.Column("status", example_status, nullable=False, server_default="draft"),
    )
    op.create_index(
        "examples_status_idx",
        "examples",
        ["status"],
        comment="supports the dashboard 'pending publish' query",
    )


def downgrade() -> None:
    op.drop_index("examples_status_idx", table_name="examples")
    op.drop_column("examples", "status")
    sa.Enum(name="example_status_enum").drop(op.get_bind(), checkfirst=True)
```

---

## Tenant-aware DB dependency (school vs independent schemas)

Per ARCH §3.16 + §4.21. The framework routes queries to the correct schema based on JWT `tenant_type` claim.

```python
# api/app/core/dependencies.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request

from app.core.security import get_claims, AuthClaims


async def get_db(
    claims: AuthClaims = Depends(get_claims),
    session_factory = Depends(get_session_factory),
) -> AsyncIterator[AsyncSession]:
    """
    Returns a session scoped to the correct schema based on JWT tenant_type.
    Repository code never reads claims.tenant_type directly — this dependency
    is the single chokepoint.
    """
    schema = "school" if claims.tenant_type == "school" else "independent"
    
    async with session_factory() as session:
        # SQLAlchemy schema_translate_map: rewrites unqualified table refs
        # to the chosen schema at query time.
        await session.connection(
            execution_options={"schema_translate_map": {None: schema}}
        )
        # Apply RLS claims for school tenant (independent tenant doesn't use RLS — single-user per micro-tenant)
        if claims.tenant_type == "school":
            await session.execute(
                text("SET LOCAL app.current_user_id = :user_id"),
                {"user_id": str(claims.sub)},
            )
            await session.execute(
                text("SET LOCAL app.current_school_id = :school_id"),
                {"school_id": str(claims.school_id)},
            )
        yield session
```

**Locked rules (per §3.16 + §4.21):**
- Repositories NEVER read `claims.tenant_type` directly. The dependency routes.
- Cross-schema FKs are forbidden — use cross-schema views per §4.21.
- Platform-shared tables (exam_frameworks, teaching_personas, etc.) live in `school` schema and the `independent` schema exposes read-only views.

---

## A dual Alembic head migration (school branch)

Per ARCH §4.21. Every migration carries an explicit branch label so CI can detect head conflicts.

```python
# alembic/versions/school/0042_add_lecture_versions.py
"""add lecture_versions table

Revision ID: a7b3c2d1e5f9
Revises: 9a2c4e6f8b1d
Create Date: 2026-05-14 12:00:00

Why:
    Per ARCH §4.18 (immutable versioning) + flow-5-teacher-creates-lecture.md §3.5,
    every save of a lecture creates a new immutable version row. This migration
    adds the lecture_versions table to support that pattern.

Rollback:
    Drop the table. No data migration needed (table is new).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a7b3c2d1e5f9"
down_revision = "9a2c4e6f8b1d"
branch_labels = ("school",)        # LOCKED: must specify branch label
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lecture_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lecture_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lectures.id", ondelete="CASCADE"),  # locked: explicit ON DELETE
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("content_jsonb", postgresql.JSONB, nullable=False),
        sa.Column("edit_mode", sa.Enum(
            "ai_generated", "text", "voice", "mixed",
            name="lecture_edit_mode",
        ), nullable=False),
        sa.Column("scores_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), 
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("lecture_id", "version_number",
                            name="uq_lecture_versions_lecture_version"),
    )
    op.create_index("lecture_versions_lecture_id_idx", "lecture_versions", ["lecture_id"])
    
    # ✗ FORBIDDEN: cross-schema FK to independent.* — never do this
    # op.create_foreign_key(..., "independent.some_table", ...)


def downgrade() -> None:
    op.drop_index("lecture_versions_lecture_id_idx", table_name="lecture_versions")
    op.drop_table("lecture_versions")
    sa.Enum(name="lecture_edit_mode").drop(op.get_bind(), checkfirst=True)
```

**For independent-branch migrations:** identical structure, but `branch_labels = ("independent",)` and lives in `alembic/versions/independent/`.

**CI guard:** every PR runs `alembic upgrade heads --sql` to detect head conflicts. Failures block merge.

---

## Vision-LLM call with image attachments

Per ARCH §8.22. The LLM abstraction handles model routing automatically when `attached_images` is non-empty.

```python
# api/app/features/lectures/service.py
from app.infrastructure.llm import llm_client
from app.infrastructure.storage import storage_client

async def answer_student_question(
    user: User,
    session: AsyncSession,
    question_text: str,
    attached_image_keys: list[str] | None = None,
) -> AnswerResponse:
    """
    Answer a student question, optionally with image attachments.
    If attached_image_keys is non-empty, routing automatically uses vision LLM.
    """
    attached_images = []
    if attached_image_keys:
        for key in attached_image_keys:
            # Per ARCH §11.19 student_question_image profile — load presigned URL or base64
            image_ref = await storage_client.get_image_ref(user=user, storage_key=key)
            attached_images.append(image_ref)
    
    # Standard call — routing decision is internal to llm_client
    response = await llm_client.chat(
        task="lecture_qa",
        messages=[
            {"role": "system", "content": load_persona_system_prompt(user)},
            {"role": "user", "content": question_text},
        ],
        attached_images=attached_images or None,  # triggers vision model if present
        stream=True,
    )
    
    return AnswerResponse(text=response.text, source_tags=response.source_tags)
```

**Locked rules (per §8.22):**
- NEVER manually choose between text and vision models. The abstraction decides.
- NEVER import `groq` / `openai` directly to "send images." All image-bearing requests go through `llm_client.chat(attached_images=...)`.
- `attached_images` is a list of `ImageRef` objects from `storage_client`, never raw bytes or paths.
- Vision model failures DO NOT fall back to text model (would silently drop image content).
