"""Tests for the upload pipeline."""

from __future__ import annotations

import pytest

from app.features.files.pipeline import _build_minio_key, _validate_magic_bytes
from app.features.files.profiles import RECOVERY_BUNDLE, get_profile, list_profiles


def test_get_profile_recovery_bundle() -> None:
    profile = get_profile("recovery_bundle")
    assert profile.name == "recovery_bundle"
    assert profile.max_size_bytes == 50 * 1024 * 1024


def test_get_profile_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_profile("nonexistent_profile")


def test_list_profiles_includes_recovery_bundle() -> None:
    assert "recovery_bundle" in list_profiles()


def test_magic_bytes_valid_pdf() -> None:
    pdf_data = b"%PDF-1.4 rest of file..."
    assert _validate_magic_bytes(pdf_data, RECOVERY_BUNDLE) is True


def test_magic_bytes_invalid_rejects() -> None:
    not_pdf = b"PK\x03\x04rest of zip file"
    assert _validate_magic_bytes(not_pdf, RECOVERY_BUNDLE) is False


def test_minio_key_format() -> None:
    key = _build_minio_key(RECOVERY_BUNDLE, "test.pdf", "upload-123", "school-456")
    assert key.startswith("recovery-bundles/school-456/")
    assert "upload-123" in key
    assert key.endswith("test.pdf")


def test_minio_key_global_scope() -> None:
    key = _build_minio_key(RECOVERY_BUNDLE, "test.pdf", "upload-123", None)
    assert "global" in key
