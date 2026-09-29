"""Vendor-neutral OpenTelemetry initialization for ProbeInterview runtimes."""

from dataclasses import dataclass

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
