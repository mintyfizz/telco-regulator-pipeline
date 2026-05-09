from telco_generator.csv_validation import CsvValidationError, validate_csv_content


def test_validate_csv_content_rejects_missing_required_columns() -> None:
    content = b"operator_id,report_period\nOPA01,2025-03\n"
    try:
        validate_csv_content(content, required_columns={"operator_id", "service_segment"})
    except CsvValidationError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("Expected CsvValidationError")


def test_validate_csv_content_rejects_schema_drift_extra_fields() -> None:
    content = b"operator_id,service_segment\nOPA01,mobile,unexpected\n"
    try:
        validate_csv_content(content, required_columns={"operator_id", "service_segment"})
    except CsvValidationError as exc:
        assert "extra fields" in str(exc)
    else:
        raise AssertionError("Expected CsvValidationError")


def test_validate_csv_content_rejects_header_only_payload() -> None:
    content = b"operator_id,service_segment\n"
    try:
        validate_csv_content(content, required_columns={"operator_id", "service_segment"})
    except CsvValidationError as exc:
        assert "no data rows" in str(exc)
    else:
        raise AssertionError("Expected CsvValidationError")


def test_validate_csv_content_accepts_valid_payload() -> None:
    content = b"operator_id,service_segment\nOPA01,mobile\n"
    rows = validate_csv_content(content, required_columns={"operator_id", "service_segment"})
    assert rows == [{"operator_id": "OPA01", "service_segment": "mobile"}]


def test_validate_csv_content_domain_payloads_trigger_quarantine_errors() -> None:
    domains = [
        "subscribers",
        "traffic_voice",
        "traffic_sms",
        "traffic_internet",
        "qos",
        "revenue",
    ]
    for domain in domains:
        content = b"operator_id,service_segment\nOPA01,mobile,unexpected\n"
        try:
            validate_csv_content(
                content,
                required_columns={"operator_id", "service_segment"},
                label=f"{domain} CSV",
            )
        except CsvValidationError as exc:
            assert "extra fields" in str(exc)
            assert domain in str(exc)
        else:
            raise AssertionError(f"Expected CsvValidationError for {domain}")
