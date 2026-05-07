"""
Upload generated CSV files to MinIO simulating operator submissions.

The path convention is:
    landing/<operator_id>/<domain>/<year>/<month>/<filename>.csv

Operator ID is parsed from the CSV content itself (each domain's CSV has
operator_id values across multiple operators in the same file). This means
we read the CSV, split by operator, and upload separate files per operator
— matching how operators would actually submit (each operator only knows
their own data).
"""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from telco_generator.uploaders.minio_client import MinioClient, MinioConfig
from telco_generator.utils.logging import get_logger

logger = get_logger(__name__)

LANDING_BUCKET = "landing"
DOMAINS = [
    "subscribers",
    "traffic_voice",
    "traffic_sms",
    "traffic_internet",
    "qos",
    "revenue",
]


@dataclass
class UploadStats:
    """Tracks upload run statistics."""

    files_uploaded: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    bytes_uploaded: int = 0


def _split_csv_by_operator(csv_path: Path) -> dict[str, list[dict]]:
    """
    Read a CSV and split rows by operator_id.

    Each domain CSV contains rows for multiple operators. To simulate real
    operator submissions, we split the file by operator before uploading.
    """
    rows_by_operator: dict[str, list[dict]] = defaultdict(list)

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            operator_id = row.get("operator_id", "UNKNOWN")
            rows_by_operator[operator_id].append(row)

    return dict(rows_by_operator)


def _rows_to_csv_bytes(rows: list[dict]) -> bytes:
    """Serialize a list of dict rows back to CSV bytes."""
    if not rows:
        return b""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _build_object_key(
    operator_id: str,
    domain: str,
    year: int,
    month: int,
) -> str:
    """Build the S3 object key following our path convention."""
    period = f"{year:04d}-{month:02d}"
    filename = f"{domain}_{period}.csv"
    return f"{operator_id}/{domain}/{year:04d}/{month:02d}/{filename}"


def _parse_period_from_filename(filename: str) -> tuple[int, int]:
    """Extract year and month from filenames like '2024-09.csv'."""
    stem = Path(filename).stem  # "2024-09"
    year_str, month_str = stem.split("-")
    return int(year_str), int(month_str)


def upload_domain_period(
    client: MinioClient,
    csv_path: Path,
    domain: str,
    skip_existing: bool = True,
) -> UploadStats:
    """
    Upload a single domain CSV (for one period) split by operator.

    The local CSV contains all operators' rows for that period. We split it
    and upload one file per operator.
    """
    stats = UploadStats()
    year, month = _parse_period_from_filename(csv_path.name)

    rows_by_operator = _split_csv_by_operator(csv_path)

    for operator_id, rows in rows_by_operator.items():
        if not rows:
            continue

        key = _build_object_key(operator_id, domain, year, month)

        if skip_existing and client.object_exists(LANDING_BUCKET, key):
            logger.debug("upload_skipped_exists", key=key)
            stats.files_skipped += 1
            continue

        # Serialize this operator's rows to CSV bytes.
        csv_bytes = _rows_to_csv_bytes(rows)

        # Write to a temporary file (boto3 upload_file expects a path).
        # Alternative: use put_object with the bytes directly.
        temp_path = csv_path.parent / f".tmp_{operator_id}_{csv_path.name}"
        temp_path.write_bytes(csv_bytes)

        try:
            metadata = {
                "operator-id": operator_id,
                "domain": domain,
                "period": f"{year:04d}-{month:02d}",
                "row-count": str(len(rows)),
                "generated-at": datetime.now(timezone.utc).isoformat(),
                "submission-type": "synthetic",
            }

            client.upload_file(
                local_path=temp_path,
                bucket=LANDING_BUCKET,
                key=key,
                metadata=metadata,
            )

            stats.files_uploaded += 1
            stats.bytes_uploaded += len(csv_bytes)

            logger.info(
                "uploaded",
                key=key,
                rows=len(rows),
                size_bytes=len(csv_bytes),
            )

        except Exception as e:
            logger.error("upload_failed", key=key, error=str(e))
            stats.files_failed += 1
        finally:
            # Clean up the temp file regardless of success/failure.
            temp_path.unlink(missing_ok=True)

    return stats


def upload_all(
    output_dir: Path,
    minio_config: MinioConfig | None = None,
    skip_existing: bool = True,
    domains: list[str] | None = None,
) -> UploadStats:
    """
    Upload all generated CSVs to MinIO.

    Walks output_dir/<domain>/<year>/<month>.csv and uploads each file
    after splitting by operator.
    """
    client = MinioClient(minio_config)
    client.ensure_bucket_exists(LANDING_BUCKET)
    client.ensure_bucket_exists("quarantine")
    client.ensure_bucket_exists("processed")

    if domains is None:
        domains = DOMAINS

    total_stats = UploadStats()

    for domain in domains:
        domain_dir = output_dir / domain
        if not domain_dir.exists():
            logger.warning("domain_dir_missing", domain=domain, path=str(domain_dir))
            continue

        # Walk year/month CSVs.
        csv_files = sorted(domain_dir.rglob("*.csv"))
        logger.info(
            "uploading_domain",
            domain=domain,
            files_found=len(csv_files),
        )

        for csv_path in csv_files:
            file_stats = upload_domain_period(
                client=client,
                csv_path=csv_path,
                domain=domain,
                skip_existing=skip_existing,
            )
            total_stats.files_uploaded += file_stats.files_uploaded
            total_stats.files_skipped += file_stats.files_skipped
            total_stats.files_failed += file_stats.files_failed
            total_stats.bytes_uploaded += file_stats.bytes_uploaded

    logger.info(
        "upload_complete",
        files_uploaded=total_stats.files_uploaded,
        files_skipped=total_stats.files_skipped,
        files_failed=total_stats.files_failed,
        mb_uploaded=round(total_stats.bytes_uploaded / 1_000_000, 2),
    )

    return total_stats
