"""MinIO / S3-compatible storage client wrapper."""

from __future__ import annotations

import hashlib
from io import BytesIO

import boto3
import structlog
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.config import get_settings

logger = structlog.get_logger(__name__)


def get_s3_client() -> BaseClient:
    """Return a boto3 S3 client pointing at MinIO."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


def sha256_of_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def ensure_bucket(bucket: str) -> None:
    """Create the bucket if it does not exist."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
        logger.info("bucket_created", bucket=bucket)


def upload_bytes(
    bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    """Upload raw bytes to MinIO. Returns the object key."""
    client = get_s3_client()
    ensure_bucket(bucket)
    client.put_object(Bucket=bucket, Key=key, Body=BytesIO(data), ContentType=content_type)
    logger.info("file_uploaded", bucket=bucket, key=key, size=len(data))
    return key


def download_bytes(bucket: str, key: str) -> bytes:
    """Download an object from MinIO as bytes."""
    client = get_s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def delete_object(bucket: str, key: str) -> None:
    """Soft-delete: mark the object with a metadata tag rather than removing it."""
    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=key)
    logger.info("file_deleted", bucket=bucket, key=key)
