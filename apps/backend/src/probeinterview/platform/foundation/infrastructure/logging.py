"""Structured logging with safe correlation context."""

import hashlib
import json
import logging
import re
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from opentelemetry import trace

from probeinterview.platform.foundation.infrastructure.telemetry import ServiceResource

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)
_client_action_id: ContextVar[str | None] = ContextVar("client_action_id", default=None)

_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/\s:@]+:[^@\s/]+@",
    flags=re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(r"\bBearer\s+[^\s,;]+", flags=re.IGNORECASE)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"\b(?:authorization|token|secret|password|api[_-]?key|"
    r"request[_-]?body|prompt|model[_-]?response)=[^\s,;]+",
    flags=re.IGNORECASE,
)

_STRUCTURED_FIELDS = (
    "summary",
    "error_code",
    "exception_type",
    "http_method",
    "http_path",
    "http_status",
    "unavailable_dependencies",
    "error_stack",
    "error_fingerprint",
)


class JsonLogFormatter(logging.Formatter):
    """Render one safe JSON object per log record."""

    def __init__(self, service_resource: ServiceResource | None = None) -> None:
        super().__init__()
        self._service_resource = service_resource

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", None)
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": redact_text(str(event if event is not None else record.getMessage())),
        }

        for field_name in _STRUCTURED_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = redact_value(value)

        trace_fields = current_trace_fields()
        for field_name, context_value in (
            ("request_id", _request_id.get()),
            ("trace_id", trace_fields.get("trace_id") or _trace_id.get()),
            ("span_id", trace_fields.get("span_id")),
            ("trace_flags", trace_fields.get("trace_flags")),
            ("client_action_id", _client_action_id.get()),
            ("job_id", _job_id.get()),
        ):
            if context_value is not None:
                payload[field_name] = context_value

        if self._service_resource is not None:
            payload.update(self._service_resource.attributes())

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(
    stream: TextIO | None = None,
    *,
    service_resource: ServiceResource | None = None,
) -> None:
    """Configure ProbeInterview loggers without changing third-party loggers."""

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonLogFormatter(service_resource))

    project_logger = logging.getLogger("probeinterview")
    project_logger.handlers = [handler]
    project_logger.setLevel(logging.INFO)
    project_logger.propagate = False


@contextmanager
def bind_log_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    client_action_id: str | None = None,
    job_id: str | None = None,
) -> Iterator[None]:
    """Bind applicable correlation identifiers for the current execution context."""

    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
    for variable, value in (
        (_request_id, request_id),
        (_trace_id, trace_id),
        (_client_action_id, client_action_id),
        (_job_id, job_id),
    ):
        if value is not None:
            tokens.append((variable, variable.set(value)))

    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def redact_value(value: object) -> object:
    """Redact strings recursively while preserving useful structured values."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def redact_text(value: str) -> str:
    """Remove common credential and private-payload forms from log text."""

    redacted = _URL_CREDENTIALS.sub(r"\g<scheme>[REDACTED]@", value)
    redacted = _BEARER_TOKEN.sub("Bearer [REDACTED]", redacted)
    return _SENSITIVE_ASSIGNMENT.sub("[REDACTED]", redacted)


def current_trace_fields() -> dict[str, str]:
    """Return standard lowercase trace correlation fields for the active span."""

    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
        "trace_flags": format(int(span_context.trace_flags), "02x"),
    }


def safe_exception_details(
    error: BaseException,
    *,
    error_code: str,
    max_frames: int = 8,
) -> dict[str, object]:
    """Describe an exception without exporting its message, locals, or raw traceback."""

    extracted = traceback.extract_tb(error.__traceback__)[-max_frames:]
    frames = [
        {
            "module": Path(frame.filename).stem,
            "function": frame.name,
            "line": frame.lineno,
        }
        for frame in extracted
    ]
    fingerprint_input = {
        "exception_type": type(error).__name__,
        "error_code": error_code,
        "frames": frames,
    }
    encoded = json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()
    return {
        "exception_type": type(error).__name__,
        "error_stack": frames,
        "error_fingerprint": hashlib.sha256(encoded).hexdigest()[:32],
    }
