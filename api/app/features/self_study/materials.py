"""Self-study material upload — T-212 (Flow 8 §3.3).

Four inputs (PDF / camera / gallery / typed) → Instant Answer (ephemeral) or
Add to Study Library (private personal pool). OCR via infrastructure.ingestion.ocr.
"""

from __future__ import annotations

from typing import Literal, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import (
    STUDENT_MATERIAL_IMAGE_MAX_BYTES,
    get_profile,
)
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.events import publish_self_study_material_uploaded
from app.features.self_study.models import (
    IndependentStudentMaterial,
    MaterialSourceType,
    SchoolStudentMaterial,
)
from app.features.self_study.schemas import (
    SelfStudyMaterialListRead,
    SelfStudyMaterialRead,
    SelfStudyMaterialTypedCreate,
    SelfStudyMaterialUploadResult,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.ingestion.extractor import extract_text_from_pdf
from app.infrastructure.ingestion.ocr import OcrUnavailableError, extract_text_from_image
from app.infrastructure.storage.client import sha256_of_bytes

logger = structlog.get_logger(__name__)

_PROFILE = "student_material"
SourceLiteral = Literal["pdf", "camera", "gallery", "typed"]
DispositionLiteral = Literal["instant_answer", "add_to_library"]


def _to_read(
    row: SchoolStudentMaterial | IndependentStudentMaterial,
    *,
    tenant_type: Literal["school", "independent"],
) -> SelfStudyMaterialRead:
    return SelfStudyMaterialRead(
        id=row.id,
        tenant_type=tenant_type,
        title=row.title,
        source_type=cast(SourceLiteral, row.source_type.value),
        book_type=(
            cast(Literal["prep_questions", "reference_content"], row.book_type.value)
            if row.book_type
            else None
        ),
        added_to_library=row.added_to_library,
        storage_key=row.storage_key,
        has_ocr_text=bool(row.ocr_text),
    )


def _is_pdf(data: bytes, filename: str) -> bool:
    return data[:4] == b"%PDF" or filename.lower().endswith(".pdf")


def _is_image(data: bytes) -> bool:
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


class SelfStudyMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    def _scope_id(
        self,
        *,
        tenant: Literal["school", "independent"],
        school_user: User | None,
        ind_user: IndependentUser | None,
    ) -> str:
        """MinIO key scope: school_id/user for school; user id for independent."""
        if tenant == "independent":
            assert ind_user is not None
            return f"independent/{ind_user.id}"
        assert school_user is not None
        return f"school/{school_user.school_id or school_user.id}/{school_user.id}"

    async def _extract_content(
        self,
        *,
        data: bytes | None,
        filename: str,
        source_type: SourceLiteral,
        typed_text: str | None,
    ) -> tuple[str, Literal["pdfplumber", "paddleocr", "tesseract", "typed"] | None]:
        if source_type == "typed":
            text = (typed_text or "").strip()
            if not text:
                raise ValidationError("Typed text is required")
            return text, "typed"

        if data is None:
            raise ValidationError("File bytes are required for this source type")

        if source_type == "pdf" or _is_pdf(data, filename):
            try:
                pages = extract_text_from_pdf(data)
                joined = "\n\n".join(str(p["text"]) for p in pages if p.get("text"))
                if not joined.strip():
                    raise ValidationError("PDF has no extractable text")
                return joined.strip(), "pdfplumber"
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        # camera / gallery images
        if len(data) > STUDENT_MATERIAL_IMAGE_MAX_BYTES:
            raise ValidationError(
                f"Image exceeds {STUDENT_MATERIAL_IMAGE_MAX_BYTES // (1024 * 1024)} MB limit"
            )
        if not _is_image(data):
            raise ValidationError("Camera/gallery uploads must be JPEG, PNG, or WEBP")
        try:
            text, method = extract_text_from_image(data)
        except OcrUnavailableError as exc:
            raise ValidationError(str(exc)) from exc
        return text, method

    def _instant_answer(self, extracted: str) -> str:
        """Ephemeral answer — full Pattern A RAG lands with later session Q&A tickets."""
        preview = extracted[:800].strip()
        return (
            "Here is what I could read from your upload (Instant Answer — "
            "not saved to your Study Library):\n\n"
            f"{preview}"
        )

    async def _emit(
        self,
        *,
        student_user_id: str,
        tenant_type: Literal["school", "independent"],
        school_id: str,
        disposition: DispositionLiteral,
        source_type: SourceLiteral,
        material_id: str | None,
        persisted: bool,
    ) -> None:
        await publish_self_study_material_uploaded(
            payload={
                "student_user_id": student_user_id,
                "tenant_type": tenant_type,
                "mode": "self_study",
                "school_id": school_id,
                "disposition": disposition,
                "source_type": source_type,
                "material_id": material_id or "",
                "persisted_to_library": persisted,
            }
        )

    async def upload_file(
        self,
        claims: dict[str, object],
        *,
        data: bytes,
        filename: str,
        source_type: SourceLiteral,
        disposition: DispositionLiteral,
        title: str,
    ) -> SelfStudyMaterialUploadResult:
        if source_type == "typed":
            raise ValidationError("Use the typed endpoint for typed materials")
        if source_type not in ("pdf", "camera", "gallery"):
            raise ValidationError("source_type must be pdf, camera, or gallery")

        tenant = get_tenant_type(claims)
        extracted, method = await self._extract_content(
            data=data,
            filename=filename,
            source_type=source_type,
            typed_text=None,
        )
        preview = extracted[:240]

        if disposition == "instant_answer":
            # Ephemeral: do NOT persist to student_materials / personal pool.
            answer = self._instant_answer(extracted)
            if tenant == "independent":
                ind_user = await self._require_independent_student(claims)
                await self._emit(
                    student_user_id=ind_user.id,
                    tenant_type="independent",
                    school_id="",
                    disposition=disposition,
                    source_type=source_type,
                    material_id=None,
                    persisted=False,
                )
            else:
                school_user = await self._require_school_student(claims)
                await self._emit(
                    student_user_id=school_user.id,
                    tenant_type="school",
                    school_id=school_user.school_id or "",
                    disposition=disposition,
                    source_type=source_type,
                    material_id=None,
                    persisted=False,
                )
            return SelfStudyMaterialUploadResult(
                disposition="instant_answer",
                source_type=source_type,
                extraction_method=method,
                material=None,
                instant_answer_text=answer,
                extracted_text_preview=preview,
                event_emitted=True,
            )

        # Add to Study Library — persist private pool row + MinIO object.
        profile = get_profile(_PROFILE)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            scope = self._scope_id(tenant="independent", school_user=None, ind_user=ind_user)
            try:
                upload = await run_upload_pipeline(
                    data=data,
                    filename=filename,
                    profile=profile,
                    session=self._session,
                    school_id=scope,
                    uploaded_by=ind_user.id,
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            record = await self._session.get(UploadRecord, upload.upload_id)
            if record is None:
                raise NotFoundError("Upload record missing after pipeline")
            ind_row = IndependentStudentMaterial(
                student_user_id=ind_user.id,
                title=title.strip() or filename,
                source_type=MaterialSourceType(source_type),
                storage_key=record.minio_key,
                ocr_text=extracted,
                file_hash=sha256_of_bytes(data),
                added_to_library=True,
            )
            self._session.add(ind_row)
            await self._session.commit()
            await self._session.refresh(ind_row)
            await self._emit(
                student_user_id=ind_user.id,
                tenant_type="independent",
                school_id="",
                disposition=disposition,
                source_type=source_type,
                material_id=ind_row.id,
                persisted=True,
            )
            logger.info("self_study_material_library_add", tenant="independent", id=ind_row.id)
            return SelfStudyMaterialUploadResult(
                disposition="add_to_library",
                source_type=source_type,
                extraction_method=method,
                material=_to_read(ind_row, tenant_type="independent"),
                instant_answer_text=None,
                extracted_text_preview=preview,
                event_emitted=True,
            )

        school_user = await self._require_school_student(claims)
        scope = self._scope_id(tenant="school", school_user=school_user, ind_user=None)
        try:
            upload = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=scope,
                uploaded_by=school_user.id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record = await self._session.get(UploadRecord, upload.upload_id)
        if record is None:
            raise NotFoundError("Upload record missing after pipeline")
        school_row = SchoolStudentMaterial(
            student_user_id=school_user.id,
            title=title.strip() or filename,
            source_type=MaterialSourceType(source_type),
            storage_key=record.minio_key,
            ocr_text=extracted,
            file_hash=sha256_of_bytes(data),
            added_to_library=True,
        )
        self._session.add(school_row)
        await self._session.commit()
        await self._session.refresh(school_row)
        await self._emit(
            student_user_id=school_user.id,
            tenant_type="school",
            school_id=school_user.school_id or "",
            disposition=disposition,
            source_type=source_type,
            material_id=school_row.id,
            persisted=True,
        )
        logger.info("self_study_material_library_add", tenant="school", id=school_row.id)
        return SelfStudyMaterialUploadResult(
            disposition="add_to_library",
            source_type=source_type,
            extraction_method=method,
            material=_to_read(school_row, tenant_type="school"),
            instant_answer_text=None,
            extracted_text_preview=preview,
            event_emitted=True,
        )

    async def submit_typed(
        self,
        claims: dict[str, object],
        payload: SelfStudyMaterialTypedCreate,
    ) -> SelfStudyMaterialUploadResult:
        text = payload.text.strip()
        tenant = get_tenant_type(claims)
        preview = text[:240]

        if payload.disposition == "instant_answer":
            answer = self._instant_answer(text)
            if tenant == "independent":
                ind_user = await self._require_independent_student(claims)
                await self._emit(
                    student_user_id=ind_user.id,
                    tenant_type="independent",
                    school_id="",
                    disposition="instant_answer",
                    source_type="typed",
                    material_id=None,
                    persisted=False,
                )
            else:
                school_user = await self._require_school_student(claims)
                await self._emit(
                    student_user_id=school_user.id,
                    tenant_type="school",
                    school_id=school_user.school_id or "",
                    disposition="instant_answer",
                    source_type="typed",
                    material_id=None,
                    persisted=False,
                )
            return SelfStudyMaterialUploadResult(
                disposition="instant_answer",
                source_type="typed",
                extraction_method="typed",
                material=None,
                instant_answer_text=answer,
                extracted_text_preview=preview,
                event_emitted=True,
            )

        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            ind_row = IndependentStudentMaterial(
                student_user_id=ind_user.id,
                title=payload.title.strip(),
                source_type=MaterialSourceType.TYPED,
                storage_key=None,
                ocr_text=text,
                file_hash=None,
                added_to_library=True,
            )
            self._session.add(ind_row)
            await self._session.commit()
            await self._session.refresh(ind_row)
            await self._emit(
                student_user_id=ind_user.id,
                tenant_type="independent",
                school_id="",
                disposition="add_to_library",
                source_type="typed",
                material_id=ind_row.id,
                persisted=True,
            )
            return SelfStudyMaterialUploadResult(
                disposition="add_to_library",
                source_type="typed",
                extraction_method="typed",
                material=_to_read(ind_row, tenant_type="independent"),
                instant_answer_text=None,
                extracted_text_preview=preview,
                event_emitted=True,
            )

        school_user = await self._require_school_student(claims)
        school_row = SchoolStudentMaterial(
            student_user_id=school_user.id,
            title=payload.title.strip(),
            source_type=MaterialSourceType.TYPED,
            storage_key=None,
            ocr_text=text,
            file_hash=None,
            added_to_library=True,
        )
        self._session.add(school_row)
        await self._session.commit()
        await self._session.refresh(school_row)
        await self._emit(
            student_user_id=school_user.id,
            tenant_type="school",
            school_id=school_user.school_id or "",
            disposition="add_to_library",
            source_type="typed",
            material_id=school_row.id,
            persisted=True,
        )
        return SelfStudyMaterialUploadResult(
            disposition="add_to_library",
            source_type="typed",
            extraction_method="typed",
            material=_to_read(school_row, tenant_type="school"),
            instant_answer_text=None,
            extracted_text_preview=preview,
            event_emitted=True,
        )

    async def list_library(self, claims: dict[str, object]) -> SelfStudyMaterialListRead:
        """Owning student only — personal pool is private (A-001)."""
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(IndependentStudentMaterial).where(
                    IndependentStudentMaterial.student_user_id == ind_user.id,
                    IndependentStudentMaterial.added_to_library.is_(True),
                    not_deleted(IndependentStudentMaterial),
                )
            )
            rows = list(result.scalars().all())
            return SelfStudyMaterialListRead(
                items=[_to_read(r, tenant_type="independent") for r in rows]
            )

        school_user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolStudentMaterial).where(
                SchoolStudentMaterial.student_user_id == school_user.id,
                SchoolStudentMaterial.added_to_library.is_(True),
                not_deleted(SchoolStudentMaterial),
            )
        )
        rows = list(result.scalars().all())
        return SelfStudyMaterialListRead(items=[_to_read(r, tenant_type="school") for r in rows])
