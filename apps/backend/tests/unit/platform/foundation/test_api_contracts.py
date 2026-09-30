import json
import logging
from collections.abc import Callable, Mapping
from io import StringIO
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from probeinterview.entrypoints.api import create_app
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_live_returns_direct_typed_resource() -> None:
    async with make_client() as client:
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


async def test_missing_request_id_generates_response_header() -> None:
    async with make_client() as client:
        response = await client.get("/health/live")

        assert UUID(response.headers["X-Request-ID"]).version == 4


async def test_valid_request_id_is_preserved() -> None:
    async with make_client() as client:
        request_id = "client-request_123"

        response = await client.get("/health/live", headers={"X-Request-ID": request_id})

        assert response.headers["X-Request-ID"] == request_id


async def test_invalid_request_id_is_replaced() -> None:
    async with make_client() as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": "not a valid request id"},
        )

        generated_request_id = response.headers["X-Request-ID"]
        assert generated_request_id != "not a valid request id"
        assert UUID(generated_request_id).version == 4


async def test_ready_returns_direct_dependency_resource() -> None:
    readiness_checks = {
        "database": passing_check,
        "task_queue": passing_check,
    }
    async with make_client(readiness_checks=readiness_checks) as client:
        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "dependencies": {
                "database": "available",
                "task_queue": "available",
            },
        }


@pytest.mark.parametrize("dependency", ["database", "task_queue"])
async def test_ready_problem_identifies_unavailable_dependency(dependency: str) -> None:
    request_id = f"{dependency}-request"
    secret = "postgresql+psycopg://user:secret@database/private"
    readiness_checks = {
        "database": passing_check,
        "task_queue": passing_check,
        dependency: failing_check(secret),
    }
    async with make_client(readiness_checks=readiness_checks) as client:
        response = await client.get(
            "/health/ready",
            headers={"X-Request-ID": request_id},
        )

        assert response.status_code == 503
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == request_id
        assert response.json() == {
            "type": "about:blank",
            "title": "Service Unavailable",
            "status": 503,
            "detail": "Required runtime dependencies are unavailable.",
            "instance": "/health/ready",
            "code": "dependencies_unavailable",
            "request_id": request_id,
            "unavailable_dependencies": [dependency],
        }
        assert secret not in response.text


async def test_validation_error_uses_safe_problem_details() -> None:
    app = make_app()

    @app.post("/test/validation")
    async def validate_payload(payload: ValidationPayload) -> ValidationPayload:
        return payload

    async with client_for_app(app) as client:
        request_id = "validation-request"
        private_token = "private-token"

        response = await client.post(
            "/test/validation",
            headers={"X-Request-ID": request_id},
            json={"token": private_token},
        )

        assert response.status_code == 422
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == request_id
        problem = response.json()
        assert problem == {
            "type": "about:blank",
            "title": "Validation Error",
            "status": 422,
            "detail": "Request validation failed.",
            "instance": "/test/validation",
            "code": "validation_error",
            "request_id": request_id,
            "errors": [
                {
                    "field": "body.token",
                    "message": "String should have at least 20 characters",
                    "code": "string_too_short",
                }
            ],
        }
        assert private_token not in response.text
        assert "input" not in response.text


async def test_unhandled_error_uses_generic_safe_problem_details() -> None:
    app = make_app()
    connection_string = "postgresql://user:secret@database/private"

    @app.get("/test/unhandled")
    async def raise_unhandled_error() -> None:
        raise RuntimeError(connection_string)

    async with client_for_app(app) as client:
        request_id = "unhandled-request"

        response = await client.get(
            "/test/unhandled",
            headers={"X-Request-ID": request_id},
        )

        assert response.status_code == 500
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == request_id
        assert response.json() == {
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred.",
            "instance": "/test/unhandled",
            "code": "internal_error",
            "request_id": request_id,
        }
        assert connection_string not in response.text
        assert "Traceback" not in response.text


async def test_http_error_uses_problem_details() -> None:
    async with make_client() as client:
        request_id = "not-found-request"

        response = await client.get(
            "/missing",
            headers={"X-Request-ID": request_id},
        )

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == request_id
        assert response.json() == {
            "type": "about:blank",
            "title": "Not Found",
            "status": 404,
            "detail": "The requested resource was not found.",
            "instance": "/missing",
            "code": "not_found",
            "request_id": request_id,
        }


async def test_request_log_preserves_request_and_trace_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with make_client() as client:
        request_id = "logged-request"

        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 200
    events = json_log_events(capsys.readouterr().err)
    completed = next(event for event in events if event["event"] == "http.request.completed")
    assert completed["request_id"] == request_id
    assert completed["trace_id"] == request_id
    assert completed["http_method"] == "GET"
    assert completed["http_path"] == "/health/live"
    assert completed["http_status"] == 200


async def test_unhandled_error_log_excludes_sensitive_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = make_app()
    sensitive_context = (
        "request_body=private-source token=private-token "
        "prompt=complete-private-prompt "
        "postgresql://user:secret@database/private"
    )

    @app.get("/test/sensitive-error")
    async def raise_sensitive_error() -> None:
        raise RuntimeError(sensitive_context)

    async with client_for_app(app) as client:
        response = await client.get(
            "/test/sensitive-error",
            headers={"X-Request-ID": "sensitive-request"},
        )

    assert response.status_code == 500
    captured = capsys.readouterr().err
    assert "private-source" not in captured
    assert "private-token" not in captured
    assert "complete-private-prompt" not in captured
    assert "user:secret" not in captured
    events = json_log_events(captured)
    failed = next(event for event in events if event["event"] == "http.request.failed")
    assert failed["request_id"] == "sensitive-request"
    assert failed["trace_id"] == "sensitive-request"
    assert failed["error_code"] == "internal_error"
    assert failed["exception_type"] == "RuntimeError"
    assert failed["summary"] == "Unhandled application error"


async def test_structured_worker_log_carries_trace_and_job_ids() -> None:
    from probeinterview.platform.foundation.infrastructure.logging import (
        JsonLogFormatter,
        bind_log_context,
    )

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("probeinterview.test.worker")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    with bind_log_context(trace_id="trace-123", job_id="job-456"):
        logger.info(
            "token=private-token postgresql://user:secret@database/private",
            extra={
                "event": "worker.job.failed",
                "summary": "Worker job failed safely",
                "error_code": "job_failed",
            },
        )

    output = stream.getvalue()
    assert "private-token" not in output
    assert "user:secret" not in output
    event = json.loads(output)
    assert event["event"] == "worker.job.failed"
    assert event["summary"] == "Worker job failed safely"
    assert event["error_code"] == "job_failed"
    assert event["trace_id"] == "trace-123"
    assert event["job_id"] == "job-456"
    assert "request_id" not in event


def make_client(
    readiness_checks: Mapping[str, Callable[[], None]] | None = None,
) -> AsyncClient:
    return client_for_app(make_app(readiness_checks=readiness_checks))


def make_app(
    readiness_checks: Mapping[str, Callable[[], None]] | None = None,
) -> FastAPI:
    if readiness_checks is None:
        return create_app(settings=make_settings())
    return create_app(
        settings=make_settings(),
        readiness_checks=readiness_checks,
    )


def client_for_app(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def passing_check() -> None:
    return None


def failing_check(message: str) -> Callable[[], None]:
    def check() -> None:
        raise RuntimeError(message)

    return check


class ValidationPayload(BaseModel):
    token: str = Field(min_length=20)


def json_log_events(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def make_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@postgres/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="test-app",
        _env_file=None,
    )
