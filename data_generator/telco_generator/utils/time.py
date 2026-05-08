"""
Time utilities for monthly period generation.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass(frozen=True)
class ReportingPeriod:
    """A single monthly reporting period."""

    year: int
    month: int

    @property
    def period_str(self) -> str:
        """Format as YYYY-MM string used in bronze tables."""
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def start_date(self) -> date:
        """First day of the period."""
        return date(self.year, self.month, 1)

    def submission_timestamp(self, day_offset: int = 5) -> datetime:
        """
        Generate a realistic submission timestamp.

        Operators typically submit reports a few days after period close.
        Default: 5 days into the following month.
        """
        if self.month == 12:
            year, month = self.year + 1, 1
        else:
            year, month = self.year, self.month + 1
        return datetime(year, month, day_offset, 14, 23, 11, tzinfo=UTC)


def generate_periods(start_year: int, end_year: int) -> list[ReportingPeriod]:
    """Generate every monthly period from start_year through end_year inclusive."""
    periods = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            periods.append(ReportingPeriod(year=year, month=month))
    return periods


def parse_reporting_period(period: str) -> ReportingPeriod:
    """Parse a YYYY-MM reporting period string."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise ValueError(f"Invalid reporting period '{period}'. Expected YYYY-MM.")
    year_str, month_str = period.split("-")
    return ReportingPeriod(year=int(year_str), month=int(month_str))


def linear_progress(period: ReportingPeriod, start_year: int, end_year: int) -> float:
    """
    Return progress through the simulation as a 0.0-1.0 float.

    Used for trajectory interpolation. period at start_year-01 returns ~0.0,
    period at end_year-12 returns ~1.0.
    """
    total_months = (end_year - start_year + 1) * 12
    elapsed_months = (period.year - start_year) * 12 + period.month - 1
    return elapsed_months / max(total_months - 1, 1)
