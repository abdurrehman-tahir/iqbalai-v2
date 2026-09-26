"""Student question-image upload HTTP API — T-166."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.student_questions.image_upload import StudentQuestionImageService
from app.features.student_questions.schemas import StudentQuestionImageUploadRead

router = APIRouter(prefix="/students/me/question-images", tags=["student-question-images"])


@router.post(
    "",
    response_model=SuccessEnvelope[StudentQuestionImageUploadRead],
    operation_id="student_upload_question_image",
    summary="Upload a student_question_image (JPEG/PNG/WEBP, ≤5 MB, EXIF stripped) (T-166)",
    status_code=201,
    dependencies=[require_role("student")],
)
async def upload_question_image(
    image: UploadFile = File(...),
    already_attached: int = Query(
        default=0,
        ge=0,
        le=3,
        description="How many images are already queued on this question (max 3 total)",
    ),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await image.read()
    result = await StudentQuestionImageService(db).upload_image(
        claims,
        data,
        image.filename or "image",
        already_attached=already_attached,
    )
    return success(result.model_dump(mode="json"))
