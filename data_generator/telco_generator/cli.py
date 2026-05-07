"""
Command-line interface for the data generator.

Usage:
    telco-generate --start-year 2024 --end-year 2024 --output-dir output/
"""

from pathlib import Path

import click

from telco_generator.config import GeneratorConfig
from telco_generator.orchestrator import run_generator
from telco_generator.utils.logging import configure_logging


@click.command()
@click.option(
    "--start-year",
    type=int,
    default=2020,
    help="First year to generate (inclusive).",
)
@click.option(
    "--end-year",
    type=int,
    default=2024,
    help="Last year to generate (inclusive).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("output"),
    help="Output directory for generated CSVs.",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducibility.",
)
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
def main(
    start_year: int,
    end_year: int,
    output_dir: Path,
    seed: int,
    log_level: str,
    json_logs: bool,
) -> None:
    """Generate synthetic Congolese telecoms operator submissions."""
    configure_logging(level=log_level, json_output=json_logs)

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


if __name__ == "__main__":
    main()