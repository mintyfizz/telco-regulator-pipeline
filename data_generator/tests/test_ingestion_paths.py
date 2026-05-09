from telco_generator.ingestion_paths import (
    PathValidationError,
    parse_segment_key,
    parse_subscriber_key,
)


def test_parse_subscriber_key_valid() -> None:
    parsed = parse_subscriber_key(
        "mobile/OPA01/subscribers/2025/03/subscribers_2025-03.csv",
        allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
    )

    assert parsed.operator_id == "OPA01"
    assert parsed.domain == "subscribers"
    assert parsed.report_period == "2025-03"


def test_parse_subscriber_key_rejects_non_csv() -> None:
    try:
        parse_subscriber_key(
            "mobile/OPA01/subscribers/2025/03/subscribers_2025-03.json",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
        )
    except PathValidationError as exc:
        assert "CSV" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_subscriber_key_rejects_invalid_path_shape() -> None:
    try:
        parse_subscriber_key(
            "mobile/OPA01/subscribers/2025/subscribers_2025-03.csv",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
        )
    except PathValidationError as exc:
        assert "Expected key format" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_subscriber_key_rejects_unsupported_segment() -> None:
    try:
        parse_subscriber_key(
            "satellite/OPA99/subscribers/2025/03/subscribers_2025-03.csv",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
        )
    except PathValidationError as exc:
        assert "Unsupported service_segment" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_segment_key_rejects_unsupported_segment_for_domain() -> None:
    try:
        parse_segment_key(
            "fixed_broadband/OPA04/traffic_sms/2025/03/traffic_sms_2025-03.csv",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
            allowed_domains={"traffic_sms", "traffic_voice"},
            domain_service_segments={
                "traffic_sms": {"mobile"},
                "traffic_voice": {"mobile", "fixed_voice"},
            },
        )
    except PathValidationError as exc:
        assert "does not submit" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_segment_key_rejects_invalid_domain() -> None:
    try:
        parse_segment_key(
            "mobile/OPA01/coverage/2025/03/coverage_2025-03.csv",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
            allowed_domains={"traffic_sms", "traffic_voice"},
            domain_service_segments={
                "traffic_sms": {"mobile"},
                "traffic_voice": {"mobile", "fixed_voice"},
            },
        )
    except PathValidationError as exc:
        assert "Unsupported domain" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_segment_key_rejects_invalid_filename_extension() -> None:
    try:
        parse_segment_key(
            "mobile/OPA01/traffic_sms/2025/03/traffic_sms_2025-03.parquet",
            allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
            allowed_domains={"traffic_sms", "traffic_voice"},
            domain_service_segments={
                "traffic_sms": {"mobile"},
                "traffic_voice": {"mobile", "fixed_voice"},
            },
        )
    except PathValidationError as exc:
        assert "not a CSV file" in str(exc)
    else:
        raise AssertionError("Expected PathValidationError")


def test_parse_segment_key_rejects_malformed_keys_for_each_domain() -> None:
    allowed_domains = {
        "traffic_voice",
        "traffic_sms",
        "traffic_internet",
        "qos",
        "revenue",
    }
    for domain in sorted(allowed_domains):
        try:
            parse_segment_key(
                f"mobile/OPA01/{domain}/2025/{domain}_2025-03.csv",
                allowed_service_segments={"mobile", "fixed_voice", "fixed_broadband"},
                allowed_domains=allowed_domains,
                domain_service_segments={
                    "traffic_voice": {"mobile", "fixed_voice"},
                    "traffic_sms": {"mobile"},
                    "traffic_internet": {"mobile", "fixed_broadband"},
                    "qos": {"mobile", "fixed_voice", "fixed_broadband"},
                    "revenue": {"mobile", "fixed_voice", "fixed_broadband"},
                },
            )
        except PathValidationError as exc:
            assert "Expected key format" in str(exc)
        else:
            raise AssertionError(f"Expected PathValidationError for malformed {domain} key")
