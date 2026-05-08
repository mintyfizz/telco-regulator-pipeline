"""
Upload generated CSV files to MinIO simulating operator submissions.

The path convention is:
    landing/<segment>/<operator_id>/<domain>/<year>/<month>/<filename>.csv

Operator ID and service segment are parsed from the CSV content itself. Each
domain CSV can contain rows across multiple segments and operators, so we split
by (service_segment, operator_id) and upload separate files per submission.
"""

import csv
import io
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
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


def _split_csv_by_segment_operator(csv_path: Path) -> dict[tuple[str, str], list[dict]]:
    """
    Read a CSV and split rows by (service_segment, operator_id).

    Each domain CSV contains rows for multiple operators and sometimes multiple
    segments for the same operator. To simulate real submissions, split before
    uploading so fixed_voice and fixed_broadband do not land in the same object.
    """
    rows_by_submission: dict[tuple[str, str], list[dict]] = defaultdict(list)

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"operator_id", "service_segment"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{csv_path} is missing required columns: {sorted(required)}")

        for line_number, row in enumerate(reader, start=2):
            operator_id = (row.get("operator_id") or "").strip()
            service_segment = (row.get("service_segment") or "").strip()
            if not operator_id:
                raise ValueError(f"{csv_path}:{line_number} has empty operator_id")
            if not service_segment:
                raise ValueError(f"{csv_path}:{line_number} has empty service_segment")
            rows_by_submission[(service_segment, operator_id)].append(row)

    return dict(rows_by_submission)


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
    service_segment: str,
    operator_id: str,
    domain: str,
    year: int,
    month: int,
) -> str:
    """
    Build the S3 object key following our segment-aware path convention.

    Path structure: <segment>/<operator>/<domain>/<year>/<month>/<file>.
    This allows multi-segment expansion in v1.1+ without path collisions.
    """
    period = f"{year:04d}-{month:02d}"
    filename = f"{domain}_{period}.csv"
    return f"{service_segment}/{operator_id}/{domain}/{year:04d}/{month:02d}/{filename}"


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

    try:
        year, month = _parse_period_from_filename(csv_path.name)
        rows_by_submission = _split_csv_by_segment_operator(csv_path)
    except Exception as e:
        logger.error(
            "upload_file_rejected",
            path=str(csv_path),
            domain=domain,
            error=str(e),
        )
        stats.files_failed += 1
        return stats

    for (service_segment, operator_id), rows in rows_by_submission.items():
        if not rows:
            continue

        key = _build_object_key(service_segment, operator_id, domain, year, month)

        if skip_existing and client.object_exists(LANDING_BUCKET, key):
            logger.debug("upload_skipped_exists", key=key)
            stats.files_skipped += 1
            continue

        # Serialize this operator's rows to CSV bytes.
        csv_bytes = _rows_to_csv_bytes(rows)

        temp_path: Path | None = None

        try:
            # Keep temp files outside output_dir so interrupted runs cannot
            # accidentally pick them up as operator submissions later.
            with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
                tmp.write(csv_bytes)
                temp_path = Path(tmp.name)

            metadata = {
                "service-segment": service_segment,
                "operator-id": operator_id,
                "domain": domain,
                "period": f"{year:04d}-{month:02d}",
                "row-count": str(len(rows)),
                "generated-at": datetime.now(UTC).isoformat(),
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
            if temp_path is not None:
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
        csv_files = sorted(
            path for path in domain_dir.rglob("*.csv")
            if not path.name.startswith(".")
        )
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
