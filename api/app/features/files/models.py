"""Upload record ORM model."""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7
from app.features.files.schemas import UploadStatus


class UploadRecord(AuditMixin, SoftDeleteMixin, Base):
    """Tracks every file uploaded through the pipeline."""

    __tablename__ = "upload_records"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    profile: Mapped[str] = mapped_column(String(100), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    minio_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[UploadStatus] = mapped_column(
        SAEnum(
            UploadStatus,
            name="upload_records_status_enum",
            schema="school",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=UploadStatus.READY,
    )
