"""Shared constants for ingestion DAG modules."""

ALLOWED_SERVICE_SEGMENTS: frozenset[str] = frozenset({"mobile", "fixed_voice", "fixed_broadband"})
