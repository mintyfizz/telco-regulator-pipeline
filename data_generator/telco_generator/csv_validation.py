"""Reusable CSV structure validation helpers for ingestion pipelines."""

import csv
import io


class CsvValidationError(ValueError):
    """Raised when CSV shape/content violates ingestion requirements."""


def validate_csv_content(
    content: bytes,
    required_columns: set[str],
    label: str = "CSV",
) -> list[dict[str, str]]:
    """Decode bytes and validate required columns, row shape, and row presence."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise CsvValidationError(f"{label} has no header row")

    missing = required_columns - set(reader.fieldnames)
    if missing:
        raise CsvValidationError(f"{label} is missing required columns: {sorted(missing)}")

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise CsvValidationError(f"{label} row {row_number} has extra fields")
        rows.append(row)

    if not rows:
        raise CsvValidationError(f"{label} has no data rows")

    return rows
