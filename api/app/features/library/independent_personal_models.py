"""Independent private pool ORM models — T-074."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class PersonalContentType(StrEnum):
    CURRICULUM = "curriculum"
    REFERENCE = "reference"


class PersonalContentStatus(StrEnum):
    PENDING = "pending"
    INGESTING = "ingesting"
    AVAILABLE = "available"
    FAILED = "failed"


class PersonalStructuredParsingStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        schema="independent",
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,
    )


class IndependentPersonalContent(AuditMixin, SoftDeleteMixin, Base):
    """Private reference material uploaded by an independent user."""

    __tablename__ = "independent_personal_content"
    __table_args__ = (
        Index("ix_independent_personal_content_user_id", "user_id"),
        Index("ix_independent_personal_content_file_sha256", "file_sha256"),
        Index("ix_independent_personal_content_deleted_at", "deleted_at"),
        Index(
            "independent_personal_content_user_sha256_uq",
            "user_id",
            "file_sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("independent.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_type: Mapped[PersonalContentType] = mapped_column(
        _pg_enum(PersonalContentType, "personalcontenttype"),
        nullable=False,
        default=PersonalContentType.REFERENCE,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PersonalContentStatus] = mapped_column(
        _pg_enum(PersonalContentStatus, "personalcontentstatus"),
        nullable=False,
        default=PersonalContentStatus.PENDING,
    )
    structured_parsing_status: Mapped[PersonalStructuredParsingStatus | None] = mapped_column(
        _pg_enum(PersonalStructuredParsingStatus, "personalstructuredparsingstatus"),
        nullable=True,
    )
    topic_tree_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    vector_collection: Mapped[str] = mapped_column(String(150), nullable=False)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
