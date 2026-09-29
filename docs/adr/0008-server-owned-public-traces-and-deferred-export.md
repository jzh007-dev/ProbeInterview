# ADR 0008: Minimal server trace propagation

## Status

Accepted

## Date

2026-09-29

## Supersedes

[ADR 0007](0007-w3c-trace-context-and-opentelemetry.md)

## Context

ADR 0007 combined public client trace continuation, production sampling,
OTLP export, exception redaction and client instrumentation in one foundation
change. That scope is disproportionate before ProbeInterview has a production
telemetry backend or a client tracing runtime.

The immediate need is smaller: correlate one server HTTP request with work it
publishes to Celery, while preserving safe structured logs.

## Decision

- Public HTTP ignores inbound `traceparent`, `tracestate` and Baggage. The API
  creates a server-owned trace and returns `X-Trace-ID` for diagnostics.
- API-to-Celery-to-Worker propagation uses W3C Trace Context.
- Backend tracing uses the official OpenTelemetry Python API/SDK plus FastAPI
  and Celery instrumentation.
- API and Worker expose stable service resource fields and logs correlate with
  the active trace/span plus request or job ID.
- Development and tests may inject the SDK in-memory exporter.
- Production OTLP export, Collector deployment, production sampling, client
  tracing, exporter redaction, retry-span topology and Agent semantics are
  deferred until a real observability backend or runtime requires them.

## Consequences

- The change remains backend-only and does not create a telemetry platform.
- Untrusted clients cannot choose the server trace ID.
- API and Worker share a standard internal trace context.
- A later observability change can add export and privacy policy without
  changing business modules.
