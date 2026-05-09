"""
Thin wrapper around boto3 S3 client configured for MinIO.

The same code works against AWS S3 in production by changing the endpoint URL
and credentials. This is the value of using boto3 over a MinIO-specific client.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from telco_generator.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MinioConfig:
    """Connection settings for MinIO."""

    endpoint_url: str = "http://localhost:9000"
    access_key: str | None = None
    secret_key: str | None = None
    region_name: str = "us-east-1"  # MinIO ignores this, but boto3 requires it

    def resolved(self) -> "MinioConfig":
        """Return a config resolved from explicit values and environment variables."""
        access_key = self.access_key or os.getenv("TELCO_MINIO_ACCESS_KEY")
        secret_key = self.secret_key or os.getenv("TELCO_MINIO_SECRET_KEY")
        endpoint_url = os.getenv("TELCO_MINIO_ENDPOINT_URL", self.endpoint_url)
        region_name = os.getenv("TELCO_MINIO_REGION", self.region_name)
        if not access_key or not secret_key:
            raise ValueError(
                "MinIO credentials are required. Provide access/secret key or set "
                "TELCO_MINIO_ACCESS_KEY and TELCO_MINIO_SECRET_KEY."
            )
        return MinioConfig(
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            region_name=region_name,
        )


class MinioClient:
    """Wraps boto3 with MinIO-friendly defaults and useful helpers."""

    def __init__(self, config: MinioConfig | None = None) -> None:
        self.config = (config or MinioConfig()).resolved()
        self._client = boto3.client(
            "s3",
            endpoint_url=self.config.endpoint_url,
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
            region_name=self.config.region_name,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def ensure_bucket_exists(self, bucket: str) -> None:
        """Create the bucket if it doesn't already exist. Idempotent."""
        try:
            self._client.head_bucket(Bucket=bucket)
            logger.debug("bucket_exists", bucket=bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                self._client.create_bucket(Bucket=bucket)
                logger.info("bucket_created", bucket=bucket)
            else:
                raise

    def object_exists(self, bucket: str, key: str) -> bool:
        """Return True if an object exists at the given bucket/key."""
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise

    def upload_file(
        self,
        local_path: Path,
        bucket: str,
        key: str,
        metadata: dict[str, str] | None = None,
        content_type: str = "text/csv",
    ) -> None:
        """
        Upload a local file to MinIO.

        Metadata keys are stored as x-amz-meta-* on the object.
        """
        extra_args: dict = {"ContentType": content_type}
        if metadata:
            # boto3 expects metadata values as strings.
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        self._client.upload_file(
            Filename=str(local_path),
            Bucket=bucket,
            Key=key,
            ExtraArgs=extra_args,
        )

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """List all object keys in a bucket matching the prefix."""
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def get_object_metadata(self, bucket: str, key: str) -> dict[str, str]:
        """Return the user metadata attached to an object."""
        response = self._client.head_object(Bucket=bucket, Key=key)
        return response.get("Metadata", {})
