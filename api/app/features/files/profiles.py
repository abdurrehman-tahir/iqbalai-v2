"""Upload profile registry per ARCH §11.

Each profile defines: allowed MIME types, magic bytes, max size, bucket, key prefix.
New profiles are added here as features land (one profile per upload surface).
"""
from __future__ import annotations

from dataclasses import dataclass, field


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

# Registry: name → profile
_REGISTRY: dict[str, UploadProfile] = {
    RECOVERY_BUNDLE.name: RECOVERY_BUNDLE,
}


def get_profile(name: str) -> UploadProfile:
    """Look up an upload profile by name. Raises KeyError if unknown."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown upload profile: '{name}'. Known profiles: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_profiles() -> list[str]:
    """Return names of all registered upload profiles."""
    return list(_REGISTRY.keys())
