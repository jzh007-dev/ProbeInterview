import json
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry import baggage
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind

from probeinterview.entrypoints.api import create_app
from probeinterview.entrypoints.worker import create_celery_app
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.asyncio

_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
_PARENT_SPAN_ID = "b7ad6b7169203331"
_TRACEPARENT = f"00-{_TRACE_ID}-{_PARENT_SPAN_ID}-01"


async def test_valid_trace_context_creates_one_server_span_with_remote_parent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exporter = InMemorySpanExporter()
    app = make_app(exporter)

    async with client_for_app(app) as client:
        response = await client.get(
            "/health/live",
            headers={
                "traceparent": _TRACEPARENT,
                "tracestate": "vendor=value",
                "X-Request-ID": "request-123",
                "X-Client-Action-ID": "action-123",
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Trace-ID"] == _TRACE_ID

    server_spans = [span for span in exporter.get_finished_spans() if span.kind is SpanKind.SERVER]
    assert len(server_spans) == 1
    server_span = server_spans[0]
    assert format(server_span.context.trace_id, "032x") == _TRACE_ID
    assert server_span.parent is not None
    assert format(server_span.parent.span_id, "016x") == _PARENT_SPAN_ID
    assert server_span.parent.trace_state.get("vendor") == "value"
    assert dict(server_span.resource.attributes) | {
        "service.namespace": "probeinterview",
        "service.name": "probeinterview-api",
        "service.version": "0.1.0",
        "deployment.environment.name": "test",
    } == dict(server_span.resource.attributes)

    completed = next(
        event
        for event in json_log_events(capsys.readouterr().err)
        if event["event"] == "http.request.completed"
    )
    assert completed["client_action_id"] == "action-123"
    assert completed["trace_id"] == _TRACE_ID
    assert completed["span_id"] == format(server_span.context.span_id, "016x")


@pytest.mark.parametrize(
    "traceparent",
    [
        None,
        "not-a-traceparent",
        "00-00000000000000000000000000000000-0000000000000000-01",
    ],
)
async def test_missing_or_invalid_trace_context_creates_new_trace(
    traceparent: str | None,
) -> None:
    exporter = InMemorySpanExporter()
    headers = {} if traceparent is None else {"traceparent": traceparent}

    async with client_for_app(make_app(exporter)) as client:
        response = await client.get("/health/live", headers=headers)

    server_span = next(
        span for span in exporter.get_finished_spans() if span.kind is SpanKind.SERVER
    )
    response_trace_id = response.headers["X-Trace-ID"]
    assert response.status_code == 200
    assert len(response_trace_id) == 32
    assert response_trace_id != "0" * 32
    assert response_trace_id == format(server_span.context.trace_id, "032x")
    assert server_span.parent is None
    root_spans = [span for span in exporter.get_finished_spans() if span.parent is None]
    assert root_spans == [server_span]


async def test_public_http_boundary_ignores_remote_sampled_flag() -> None:
    exporter = InMemorySpanExporter()
    app = create_app(
        settings=production_settings(telemetry_trace_sample_ratio=0.0),
        readiness_checks=passing_checks(),
        telemetry_span_exporter=exporter,
    )

    async with client_for_app(app) as client:
        response = await client.get("/health/live", headers={"traceparent": _TRACEPARENT})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == _TRACE_ID
    assert exporter.get_finished_spans() == ()


async def test_baggage_and_invalid_client_action_are_ignored(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exporter = InMemorySpanExporter()
    app = make_app(exporter)

    @app.get("/test/context")
    async def inspect_context() -> dict[str, object]:
        return {"baggage": dict(baggage.get_all())}

    private_value = "private-user-payload"
    async with client_for_app(app) as client:
        response = await client.get(
            "/test/context",
            headers={
                "traceparent": _TRACEPARENT,
                "baggage": f"actor={private_value}",
                "X-Client-Action-ID": "invalid client action",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"baggage": {}}
    captured = capsys.readouterr().err
    assert private_value not in captured
    completed = next(
        event for event in json_log_events(captured) if event["event"] == "http.request.completed"
    )
    assert "client_action_id" not in completed
    for span in exporter.get_finished_spans():
        assert private_value not in json.dumps(dict(span.attributes or {}))


async def test_problem_details_response_keeps_trace_diagnostics() -> None:
    exporter = InMemorySpanExporter()

    async with client_for_app(make_app(exporter)) as client:
        response = await client.get("/missing", headers={"traceparent": _TRACEPARENT})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["X-Trace-ID"] == _TRACE_ID


async def test_query_values_are_excluded_from_span_telemetry() -> None:
    exporter = InMemorySpanExporter()
    private_query = "PRIVATE_QUERY_SENTINEL"

    async with client_for_app(make_app(exporter)) as client:
        response = await client.get(f"/health/live?token={private_query}")

    assert response.status_code == 200
    assert private_query not in exported_telemetry(exporter)


async def test_exception_messages_and_tracebacks_are_excluded_from_spans() -> None:
    exporter = InMemorySpanExporter()
    private_message = "PRIVATE_EXCEPTION_SENTINEL"
    app = make_app(exporter)

    @app.get("/test/private-exception")
    async def raise_private_exception() -> None:
        raise RuntimeError(private_message)

    async with client_for_app(app) as client:
        response = await client.get("/test/private-exception")

    assert response.status_code == 500
    assert private_message not in exported_telemetry(exporter)
    assert "Traceback" not in exported_telemetry(exporter)


async def test_worker_telemetry_uses_stable_service_resource() -> None:
    celery_app = create_celery_app(settings=make_test_settings())
    telemetry = celery_app.probeinterview_telemetry

    assert telemetry.resource.attributes() == {
        "service.namespace": "probeinterview",
        "service.name": "probeinterview-worker",
        "service.version": "0.1.0",
        "deployment.environment.name": "test",
    }


def make_app(exporter: InMemorySpanExporter) -> FastAPI:
    return create_app(
        settings=make_test_settings(),
        readiness_checks=passing_checks(),
        telemetry_span_exporter=exporter,
    )


def client_for_app(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def passing_checks() -> dict[str, Callable[[], None]]:
    return {
        "database": lambda: None,
        "task_queue": lambda: None,
    }


def make_test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@postgres/probe",
        celery_broker_url="redis://redis:6379/0",
        _env_file=None,
    )


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://probe:probe@postgres/probe",
        "celery_broker_url": "redis://redis:6379/0",
        "local_actor_enabled": False,
        "foundation_probe_enabled": False,
        "object_storage_adapter": "oss",
        "embedding_adapter": "bailian",
        "structured_llm_adapter": "bailian",
        "oss_endpoint": "https://oss.example.invalid",
        "oss_bucket": "probeinterview",
        "oss_access_key_id": "access-key",
        "oss_access_key_secret": "access-secret",
        "bailian_api_key": "bailian-key",
    }
    values.update(overrides)
    return Settings(**values, _env_file=None)


def json_log_events(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def exported_telemetry(exporter: InMemorySpanExporter) -> str:
    exported = []
    for span in exporter.get_finished_spans():
        exported.append(
            {
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "events": [
                    {
                        "name": event.name,
                        "attributes": dict(event.attributes or {}),
                    }
                    for event in span.events
                ],
            }
        )
    return json.dumps(exported, sort_keys=True)
