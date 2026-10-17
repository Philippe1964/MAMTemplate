"""Request correlation ID context and structured JSON stdout logging (12-Factor XI)."""

import datetime
import json
import logging
import sys
import uuid
from contextvars import ContextVar

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the correlation X-Request-ID bound to the current async execution context.

    Returns:
        Current request correlation identifier or '-' if outside a request.
    """
    return _request_id_ctx.get()


def set_request_id(request_id: str | None = None) -> str:
    """Bind a correlation X-Request-ID to the current async execution context.

    Args:
        request_id: Incoming correlation ID; generates a new UUIDv4 if omitted or blank.

    Returns:
        The active correlation ID stored in context.
    """
    clean_id = (request_id or "").strip() or str(uuid.uuid4())
    _request_id_ctx.set(clean_id)
    return clean_id


class StructuredJsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON objects with correlation request_id."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a LogRecord into a Cloud-Native JSON string.

        Args:
            record: Standard Python LogRecord.

        Returns:
            Single-line JSON string.
        """
        payload = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger to emit structured JSON records to stdout.

    Args:
        level: Minimum logging level.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonLogFormatter())
    root_logger = logging.getLogger()
    if not any(
        isinstance(getattr(h, "formatter", None), StructuredJsonLogFormatter)
        for h in root_logger.handlers
    ):
        root_logger.addHandler(handler)
    root_logger.setLevel(level)
