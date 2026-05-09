from telco_generator.pipeline_runtime import classify_period_status


def test_classify_period_status_loaded() -> None:
    counts = {
        "subscribers": 1,
        "traffic_voice": 1,
        "traffic_sms": 1,
        "traffic_internet": 1,
        "qos": 1,
        "revenue": 1,
    }
    assert classify_period_status(counts) == "loaded"


def test_classify_period_status_partial() -> None:
    counts = {
        "subscribers": 1,
        "traffic_voice": 0,
        "traffic_sms": 0,
        "traffic_internet": 0,
        "qos": 0,
        "revenue": 0,
    }
    assert classify_period_status(counts) == "partial"


def test_classify_period_status_empty() -> None:
    counts = {
        "subscribers": 0,
        "traffic_voice": 0,
        "traffic_sms": 0,
        "traffic_internet": 0,
        "qos": 0,
        "revenue": 0,
    }
    assert classify_period_status(counts) == "empty"
