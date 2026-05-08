"""
Command-line interface for the data generator and uploader.

Usage:
    telco-generate generate --start-year 2020 --end-year 2024
    telco-generate upload --output-dir output/
    telco-generate verify
"""

from pathlib import Path

import click

from telco_generator.config import GeneratorConfig
from telco_generator.orchestrator import run_generator
from telco_generator.uploaders.minio_client import MinioClient, MinioConfig
from telco_generator.uploaders.minio_uploader import upload_all
from telco_generator.utils.logging import configure_logging


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
)
@click.option(
    "--json-logs",
    is_flag=True,
    default=False,
    help="Emit JSON-formatted logs.",
)
def main(log_level: str, json_logs: bool) -> None:
    """Telco regulator pipeline: data generator and uploader."""
    configure_logging(level=log_level, json_output=json_logs)


@main.command()
@click.option("--start-year", type=int, default=2020)
@click.option("--end-year", type=int, default=2024)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("output"),
)
@click.option("--seed", type=int, default=42)
def generate(
    start_year: int,
    end_year: int,
    output_dir: Path,
    seed: int,
) -> None:
    """Generate synthetic operator submissions as local CSVs."""
    config = GeneratorConfig(
        output_dir=output_dir,
        start_year=start_year,
        end_year=end_year,
        random_seed=seed,
    )
    totals = run_generator(config)

    click.echo("\nGeneration complete:")
    for domain, count in totals.items():
        click.echo(f"  {domain}: {count:,} rows")


@main.command()
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("output"),
    help="Directory containing generated CSVs to upload.",
)
@click.option(
    "--endpoint",
    default="http://localhost:9000",
    help="MinIO endpoint URL.",
)
@click.option(
    "--access-key",
    default="minio_admin",
    help="MinIO access key.",
)
@click.option(
    "--secret-key",
    default="changeme_local_only",
    help="MinIO secret key.",
)
@click.option(
    "--skip-existing/--overwrite",
    default=True,
    help="Skip files that already exist in MinIO (default) or overwrite them.",
)
@click.option(
    "--domain",
    "domains",
    multiple=True,
    type=click.Choice([
        "subscribers", "traffic_voice", "traffic_sms",
        "traffic_internet", "qos", "revenue",
    ]),
    help="Specific domains to upload (default: all).",
)
def upload(
    output_dir: Path,
    endpoint: str,
    access_key: str,
    secret_key: str,
    skip_existing: bool,
    domains: tuple[str, ...],
) -> None:
    """Upload generated CSVs to MinIO landing bucket."""
    config = MinioConfig(
        endpoint_url=endpoint,
        access_key=access_key,
        secret_key=secret_key,
    )

    domain_list = list(domains) if domains else None

    try:
        stats = upload_all(
            output_dir=output_dir,
            minio_config=config,
            skip_existing=skip_existing,
            domains=domain_list,
        )
    except Exception as e:
        raise click.ClickException(f"Upload failed before completion: {e}") from e

    click.echo("\nUpload complete:")
    click.echo(f"  Files uploaded: {stats.files_uploaded:,}")
    click.echo(f"  Files skipped:  {stats.files_skipped:,}")
    click.echo(f"  Files failed:   {stats.files_failed:,}")
    click.echo(f"  Total size:     {stats.bytes_uploaded / 1_000_000:.2f} MB")

    if stats.files_failed:
        raise click.ClickException(
            f"{stats.files_failed:,} file(s) failed to upload"
        )


@main.command()
@click.option("--endpoint", default="http://localhost:9000")
@click.option("--access-key", default="minio_admin")
@click.option("--secret-key", default="changeme_local_only")
def verify(endpoint: str, access_key: str, secret_key: str) -> None:
    """Verify MinIO contents — count files per bucket and per operator."""
    config = MinioConfig(
        endpoint_url=endpoint,
        access_key=access_key,
        secret_key=secret_key,
    )
    client = MinioClient(config)
    errors: list[str] = []

    for bucket in ("landing", "quarantine", "processed"):
        try:
            keys = client.list_objects(bucket)
            click.echo(f"\nBucket '{bucket}': {len(keys):,} objects")

            if keys:
                # Group by segment, operator, and domain for any bucket.
                by_segment: dict[str, int] = {}
                by_operator: dict[str, int] = {}
                by_domain: dict[str, int] = {}
                for key in keys:
                    parts = key.split("/")
                    if len(parts) >= 3:
                        segment = parts[0]
                        op_id = parts[1]
                        domain = parts[2]
                        by_segment[segment] = by_segment.get(segment, 0) + 1
                        by_operator[op_id] = by_operator.get(op_id, 0) + 1
                        by_domain[domain] = by_domain.get(domain, 0) + 1

                click.echo("  By segment:")
                for segment in sorted(by_segment):
                    click.echo(f"    {segment}: {by_segment[segment]:,}")
                click.echo("  By operator:")
                for op_id in sorted(by_operator):
                    click.echo(f"    {op_id}: {by_operator[op_id]:,}")
                click.echo("  By domain:")
                for domain in sorted(by_domain):
                    click.echo(f"    {domain}: {by_domain[domain]:,}")

        except Exception as e:
            message = f"Bucket '{bucket}': error — {e}"
            click.echo(f"\n{message}")
            errors.append(message)

    if errors:
        raise click.ClickException(
            "MinIO verification failed: " + "; ".join(errors)
        )


if __name__ == "__main__":
    main()
