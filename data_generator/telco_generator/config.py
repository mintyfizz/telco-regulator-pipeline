"""
Configuration models for the data generator.

Pydantic enforces types and constraints on configuration objects.
The default configuration is appropriate for the full 5-year synthetic dataset.
"""

from pathlib import Path

from pydantic import BaseModel, Field


class GeneratorConfig(BaseModel):
    """Top-level configuration for a generator run."""

    # Output settings.
    output_dir: Path = Field(default=Path("output"))
    output_format: str = Field(default="csv", pattern="^(csv|parquet|jsonl)$")

    # Time range.
    start_year: int = Field(default=2020, ge=2018, le=2030)
    end_year: int = Field(default=2024, ge=2018, le=2030)
    period: str | None = Field(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Optional single reporting period in YYYY-MM format.",
    )

    # Determinism.
    random_seed: int | None = Field(default=42)

    # Noise injection — higher values produce noisier data.
    noise_level: float = Field(default=0.05, ge=0.0, le=0.5)

    # Anomaly injection rates.
    qos_gaming_rate: float = Field(default=0.03, ge=0.0, le=0.5)
    submission_error_rate: float = Field(default=0.01, ge=0.0, le=0.5)
    anomaly_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=0.5,
        description="Row-level controlled anomaly rate for suspicious submissions.",
    )

    # Domains to generate (allows partial runs).
    domains: list[str] = Field(
        default=[
            "subscribers",
            "traffic_voice",
            "traffic_sms",
            "traffic_internet",
            "qos",
            "revenue",
        ]
    )

    # Operators and regions to include (empty list = all).
    operators: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


def get_default_config() -> GeneratorConfig:
    """Return the default generator configuration."""
    return GeneratorConfig()
