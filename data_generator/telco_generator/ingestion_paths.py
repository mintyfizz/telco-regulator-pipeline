"""Reusable object-key parsing helpers for ingestion pipelines."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedObjectKey:
    """Normalized parsed key details for segmented submission objects."""

    service_segment: str
    operator_id: str
    domain: str
    year: str
    month: str
    filename: str

    @property
    def report_period(self) -> str:
        return f"{self.year}-{self.month}"


class PathValidationError(ValueError):
    """Raised when an object key does not match expected path conventions."""


def parse_subscriber_key(key: str, allowed_service_segments: set[str]) -> ParsedObjectKey:
    """Parse and validate a subscriber landing object key."""
    parts = key.split("/")
    if len(parts) != 6:
        raise PathValidationError(
            "Expected key format: <segment>/<operator>/subscribers/<year>/<month>/<file>.csv"
        )

    service_segment, operator_id, domain, year, month, filename = parts
    if domain != "subscribers":
        raise PathValidationError("Expected domain 'subscribers'")
    if service_segment not in allowed_service_segments:
        raise PathValidationError(f"Unsupported service_segment: {service_segment}")
    if not filename.endswith(".csv"):
        raise PathValidationError("Object is not a CSV file")

    return ParsedObjectKey(
        service_segment=service_segment,
        operator_id=operator_id,
        domain=domain,
        year=year,
        month=month,
        filename=filename,
    )


def parse_segment_key(
    key: str,
    allowed_service_segments: set[str],
    allowed_domains: set[str],
    domain_service_segments: dict[str, set[str]],
) -> ParsedObjectKey:
    """Parse and validate a non-subscriber segmented-domain object key."""
    parts = key.split("/")
    if len(parts) != 6:
        raise PathValidationError(
            "Expected key format: <segment>/<operator>/<domain>/<year>/<month>/<file>.csv"
        )

    service_segment, operator_id, domain, year, month, filename = parts
    if service_segment not in allowed_service_segments:
        raise PathValidationError(f"Unsupported service_segment: {service_segment}")
    if domain not in allowed_domains:
        raise PathValidationError(f"Unsupported domain: {domain}")
    if service_segment not in domain_service_segments[domain]:
        raise PathValidationError(f"Segment {service_segment} does not submit domain {domain}")
    if not filename.endswith(".csv"):
        raise PathValidationError("Object is not a CSV file")

    return ParsedObjectKey(
        service_segment=service_segment,
        operator_id=operator_id,
        domain=domain,
        year=year,
        month=month,
        filename=filename,
    )
