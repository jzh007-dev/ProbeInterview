"""Structured logging with safe correlation context."""

import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import TextIO

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)

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
)


class JsonLogFormatter(logging.Formatter):
    """Render one safe JSON object per log record."""

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

        for field_name, context_value in (
            ("request_id", _request_id.get()),
            ("trace_id", _trace_id.get()),
            ("job_id", _job_id.get()),
        ):
            if context_value is not None:
                payload[field_name] = context_value

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(stream: TextIO | None = None) -> None:
    """Configure ProbeInterview loggers without changing third-party loggers."""

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonLogFormatter())

    project_logger = logging.getLogger("probeinterview")
    project_logger.handlers = [handler]
    project_logger.setLevel(logging.INFO)
    project_logger.propagate = False


@contextmanager
def bind_log_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    job_id: str | None = None,
) -> Iterator[None]:
    """Bind applicable correlation identifiers for the current execution context."""

    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
    for variable, value in (
        (_request_id, request_id),
        (_trace_id, trace_id),
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
    return value


def redact_text(value: str) -> str:
    """Remove common credential and private-payload forms from log text."""

    redacted = _URL_CREDENTIALS.sub(r"\g<scheme>[REDACTED]@", value)
    redacted = _BEARER_TOKEN.sub("Bearer [REDACTED]", redacted)
    return _SENSITIVE_ASSIGNMENT.sub("[REDACTED]", redacted)
