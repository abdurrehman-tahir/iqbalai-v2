"""Upload profile registry per ARCH §11.

Each profile defines: allowed MIME types, magic bytes, max size, bucket, key prefix.
New profiles are added here as features land (one profile per upload surface).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadProfile:
    """Configuration for a single upload surface."""

    name: str
    bucket: str
    key_prefix: str
    allowed_mime_types: frozenset[str]
    magic_bytes: list[bytes]  # first N bytes that must match for validation
    max_size_bytes: int
    description: str = ""
    # When True, the upload pipeline re-encodes the image and strips EXIF (T-166).
    strip_exif: bool = False
    # Soft retention hint for purge jobs (None = indefinite). Days since created_at.
    retention_days: int | None = None


# ── Profile registry ──────────────────────────────────────────────────────────
# Add profiles here as milestones land. Each profile corresponds to one upload surface.

RECOVERY_BUNDLE = UploadProfile(
    name="recovery_bundle",
    bucket="pdfs",
    key_prefix="recovery-bundles",
    allowed_mime_types=frozenset({"application/pdf"}),
    magic_bytes=[b"%PDF"],
    max_size_bytes=50 * 1024 * 1024,  # 50 MB
    description="Student recovery bundle PDF — uploaded by teacher",
)

PLATFORM_REFERENCE_BOOK = UploadProfile(
    name="platform_reference_book",
    bucket="pdfs",
    key_prefix="platform-library",
    allowed_mime_types=frozenset({"application/pdf"}),
    magic_bytes=[b"%PDF"],
    max_size_bytes=100 * 1024 * 1024,  # 100 MB per ARCH §11.19
    description="Platform-level reference book — uploaded by Platform Admin; global SHA-256 dedup",
)

SCHOOL_LIBRARY_CONTENT = UploadProfile(
    name="school_library_content",
    bucket="pdfs",
    key_prefix="school-library",
    allowed_mime_types=frozenset({"application/pdf"}),
    magic_bytes=[b"%PDF"],
    max_size_bytes=100 * 1024 * 1024,  # 100 MB per ARCH §11.19
    description="School library PDF — per-school SHA-256 dedup (Flow 3 §3.3/§3.4)",
)

INDEPENDENT_PERSONAL_CONTENT = UploadProfile(
    name="independent_personal_content",
    bucket="pdfs",
    key_prefix="independent-personal",
    allowed_mime_types=frozenset({"application/pdf"}),
    magic_bytes=[b"%PDF"],
    max_size_bytes=100 * 1024 * 1024,  # 100 MB per ARCH §11.19
    description="Independent user private reference PDF — per-user SHA-256 dedup",
)

LECTURE_IMAGE = UploadProfile(
    name="lecture_image",
    # No "images" entry in ARCH §11.3's older bucket enum (pdfs/audio/va-uploads/
    # exports/ml-models) — §11.19's newer consolidated table locks lecture_image's
    # limits but not its bucket name. BULK_IMPORT already precedents a bucket
    # outside that enum ("imports"), so a dedicated "images" bucket follows the
    # same content-type-scoping rule (§11.1) without colliding with "pdfs".
    bucket="images",
    key_prefix="lecture-image",
    allowed_mime_types=frozenset({"image/jpeg", "image/png", "image/gif"}),
    magic_bytes=[b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a"],
    max_size_bytes=5 * 1024 * 1024,  # 5 MB per ARCH §11.19
    description="Teacher-embedded image in the lecture TipTap editor (Flow 5 §3.5, T-132)",
)

# WEBP uses a sentinel magic token (see pipeline._validate_magic_bytes) because
# the RIFF container header alone is not format-specific — we also check bytes 8-11.
_WEBP_MAGIC_SENTINEL = b"WEBP"

STUDENT_QUESTION_IMAGE = UploadProfile(
    name="student_question_image",
    bucket="images",
    key_prefix="student-question-image",
    allowed_mime_types=frozenset({"image/jpeg", "image/png", "image/webp"}),
    magic_bytes=[b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", _WEBP_MAGIC_SENTINEL],
    max_size_bytes=5 * 1024 * 1024,  # 5 MB per ARCH §11.19
    description=(
        "Student-attached image on a lecture Q&A question (Flow 6 §3.5 / T-166). "
        "JPEG/PNG/WEBP only; GIF rejected; EXIF stripped; 1-year retention; "
        "max 3 images per question enforced at submit."
    ),
    strip_exif=True,
    retention_days=365,
)

BULK_IMPORT = UploadProfile(
    name="bulk_import",
    bucket="imports",
    key_prefix="bulk-imports",
    allowed_mime_types=frozenset(
        {
            "text/csv",
            "application/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    ),
    magic_bytes=[b"PK\x03\x04"],  # XLSX; CSV skips magic check in pipeline caller
    max_size_bytes=5 * 1024 * 1024,  # 5 MB per Flow 2 §6
    description="Coordinator student bulk import — CSV/XLSX, dry-run validation (T-037)",
)

# Registry: name → profile
_REGISTRY: dict[str, UploadProfile] = {
    RECOVERY_BUNDLE.name: RECOVERY_BUNDLE,
    PLATFORM_REFERENCE_BOOK.name: PLATFORM_REFERENCE_BOOK,
    SCHOOL_LIBRARY_CONTENT.name: SCHOOL_LIBRARY_CONTENT,
    INDEPENDENT_PERSONAL_CONTENT.name: INDEPENDENT_PERSONAL_CONTENT,
    LECTURE_IMAGE.name: LECTURE_IMAGE,
    STUDENT_QUESTION_IMAGE.name: STUDENT_QUESTION_IMAGE,
    BULK_IMPORT.name: BULK_IMPORT,
}

# Soft limit: max images attachable to one student question (ARCH §11.19 / §8.22).
STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION = 3


def get_profile(name: str) -> UploadProfile:
    """Look up an upload profile by name. Raises KeyError if unknown."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown upload profile: '{name}'. Known profiles: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_profiles() -> list[str]:
    """Return names of all registered upload profiles."""
    return list(_REGISTRY.keys())
