"""Pure decision helpers shared by monthly orchestration logic and tests."""


def classify_period_status(
    counts: dict[str, int],
    required_domains: tuple[str, ...] = (
        "subscribers",
        "traffic_voice",
        "traffic_sms",
        "traffic_internet",
        "qos",
        "revenue",
    ),
) -> str:
    """Classify monthly period state as loaded, partial, or empty."""
    loaded = [domain for domain in required_domains if int(counts.get(domain, 0)) > 0]
    if len(loaded) == len(required_domains):
        return "loaded"
    if loaded:
        return "partial"
    return "empty"
