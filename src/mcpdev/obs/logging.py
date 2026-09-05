"""Structured logs, correlated with traces, on stderr."""

import json
import logging
import sys
from typing import Any

from opentelemetry import trace


class TraceCorrelatedJSON(logging.Formatter):
    """One JSON object per line, carrying the active trace."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            payload["trace_id"] = format(context.trace_id, "032x")
            payload["span_id"] = format(context.span_id, "016x")
        if record.exc_info:
            payload["error"] = record.exc_info[0].__name__
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: str = "INFO") -> None:
    """Send everything to stderr. Never stdout."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(TraceCorrelatedJSON())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
