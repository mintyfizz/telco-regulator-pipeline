"""
MinIO interaction helpers for Airflow tasks.

These wrappers use the Airflow connection named telco_minio and expose only the
S3 operations the ingestion DAG needs: list, download, copy, delete, and move.
"""

from typing import Any

import boto3
from airflow.hooks.base import BaseHook
from botocore.client import Config


def get_minio_client() -> Any:
    conn = BaseHook.get_connection("telco_minio")
    extra = conn.extra_dejson
    return boto3.client(
        "s3",
        endpoint_url=extra.get("endpoint_url", "http://telco_minio:9000"),
        aws_access_key_id=conn.login,
        aws_secret_access_key=conn.password,
        region_name=extra.get("region_name", "us-east-1"),
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def list_objects(bucket: str, prefix: str = "") -> list[str]:
    client = get_minio_client()
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def download_object(bucket: str, key: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def get_object_size(bucket: str, key: str) -> int:
    client = get_minio_client()
    response = client.head_object(Bucket=bucket, Key=key)
    return response["ContentLength"]


def get_object_metadata(bucket: str, key: str) -> dict[str, str]:
    client = get_minio_client()
    response = client.head_object(Bucket=bucket, Key=key)
    return response.get("Metadata", {})


def copy_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    additional_metadata: dict[str, str] | None = None,
) -> None:
    client = get_minio_client()
    existing = get_object_metadata(source_bucket, source_key)
    merged = {**existing, **(additional_metadata or {})}
    client.copy_object(
        Bucket=dest_bucket,
        Key=dest_key,
        CopySource={"Bucket": source_bucket, "Key": source_key},
        Metadata=merged,
        MetadataDirective="REPLACE",
    )


def delete_object(bucket: str, key: str) -> None:
    client = get_minio_client()
    client.delete_object(Bucket=bucket, Key=key)


def move_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    additional_metadata: dict[str, str] | None = None,
) -> None:
    # S3 has no atomic move; copy-then-delete is the standard pattern.
    # If delete fails after copy, result is a duplicate not data loss.
    copy_object(source_bucket, source_key, dest_bucket, dest_key, additional_metadata)
    delete_object(source_bucket, source_key)
