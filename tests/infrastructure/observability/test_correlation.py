"""Unit tests for Cloud-Native correlation ID context and structured JSON log formatting."""

import json
import logging

from mamtemplate.infrastructure.observability.correlation import (
    StructuredJsonLogFormatter,
    get_request_id,
    set_request_id,
)


def test_set_and_get_request_id_generates_or_preserves_id() -> None:
    """Verify set_request_id preserves provided IDs and generates UUIDv4 when empty."""
    explicit = set_request_id("req-cloud-123")
    assert explicit == "req-cloud-123"
    assert get_request_id() == "req-cloud-123"

    generated = set_request_id("")
    assert len(generated) >= 32
    assert get_request_id() == generated


def test_structured_json_log_formatter_includes_request_id() -> None:
    """Verify StructuredJsonLogFormatter serializes log records as JSON with request_id."""
    set_request_id("trace-abc-999")
    formatter = StructuredJsonLogFormatter()
    record = logging.LogRecord(
        name="mamtemplate.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Cloud-native log message",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)
    parsed = json.loads(rendered)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "mamtemplate.test"
    assert parsed["message"] == "Cloud-native log message"
    assert parsed["request_id"] == "trace-abc-999"
    assert "timestamp" in parsed
