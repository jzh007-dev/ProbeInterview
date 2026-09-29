"""Vendor-neutral OpenTelemetry initialization for ProbeInterview runtimes."""

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace.span import Span

from probeinterview.platform.foundation.infrastructure.settings import Settings

SERVICE_NAMESPACE = "probeinterview"
API_SERVICE_NAME = "probeinterview-api"
WORKER_SERVICE_NAME = "probeinterview-worker"


@dataclass(frozen=True)
class ServiceResource:
    """Stable service identity shared by spans and structured logs."""

    namespace: str
    name: str
    version: str
    environment: str

    def attributes(self) -> dict[str, str]:
        """Return standard OpenTelemetry resource attributes."""

        return {
            "service.namespace": self.namespace,
            "service.name": self.name,
            "service.version": self.version,
            "deployment.environment.name": self.environment,
        }


@dataclass(frozen=True)
class TelemetryRuntime:
    """Initialized tracing runtime owned by one API or Worker process."""

    tracer_provider: TracerProvider
    resource: ServiceResource

    def shutdown(self) -> None:
        """Flush and stop processors without changing business outcomes."""

        self.tracer_provider.shutdown()


def initialize_telemetry(
    settings: Settings,
    *,
    service_name: str,
    span_exporter: SpanExporter | None = None,
) -> TelemetryRuntime:
    """Create an isolated provider and install Trace Context-only propagation."""

    set_global_textmap(TraceContextTextMapPropagator())
    service_resource = ServiceResource(
        namespace=SERVICE_NAMESPACE,
        name=service_name,
        version=settings.service_version,
        environment=settings.environment,
    )
    provider = TracerProvider(
        resource=Resource.create(service_resource.attributes()),
        sampler=build_sampler(settings),
    )
    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return TelemetryRuntime(tracer_provider=provider, resource=service_resource)


def build_sampler(settings: Settings) -> Sampler:
    """Build a sampler that never trusts a remote parent's sampled bit."""

    ratio = settings.telemetry_trace_sample_ratio
    if ratio is None:
        root_sampler: Sampler = ALWAYS_ON if settings.environment != "production" else ALWAYS_OFF
    else:
        root_sampler = TraceIdRatioBased(ratio)

    return ParentBased(
        root=root_sampler,
        remote_parent_sampled=root_sampler,
        remote_parent_not_sampled=root_sampler,
        local_parent_sampled=ALWAYS_ON,
        local_parent_not_sampled=ALWAYS_OFF,
    )


def instrument_fastapi_app(app: FastAPI, telemetry: TelemetryRuntime) -> None:
    """Instrument FastAPI once with infrastructure-owned privacy controls."""

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=telemetry.tracer_provider,
        server_request_hook=_sanitize_server_request_span,
        exclude_spans=["receive", "send"],
    )


def _sanitize_server_request_span(span: Span, scope: dict[str, Any]) -> None:
    """Strip query values from legacy and current HTTP URL attributes."""

    if not span.is_recording():
        return

    path = str(scope.get("path") or "/")
    root_path = str(scope.get("root_path") or "")
    safe_path = f"{root_path}{path}"
    scheme = str(scope.get("scheme") or "http")
    server = scope.get("server")
    if isinstance(server, tuple) and len(server) == 2:
        host, port = server
        default_port = 443 if scheme == "https" else 80
        authority = str(host) if port in (None, default_port) else f"{host}:{port}"
        safe_url = f"{scheme}://{authority}{safe_path}"
    else:
        safe_url = safe_path

    span.set_attribute("http.url", safe_url)
    span.set_attribute("http.target", safe_path)
    span.set_attribute("url.full", safe_url)
    span.set_attribute("url.query", "")
