"""FastAPI process entrypoint."""

import logging
import re
from collections.abc import Callable, Mapping
from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export import SpanExporter
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import State
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from probeinterview.platform.foundation.api.contracts import (
    FieldViolation,
    HealthResource,
    ProblemDetails,
    ReadinessResource,
)
from probeinterview.platform.foundation.api.problems import problem_response
from probeinterview.platform.foundation.infrastructure.logging import (
    bind_log_context,
    configure_logging,
    safe_exception_details,
)
from probeinterview.platform.foundation.infrastructure.readiness import (
    ReadinessCheck,
    build_readiness_checks,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings
from probeinterview.platform.foundation.infrastructure.telemetry import (
    API_SERVICE_NAME,
    initialize_telemetry,
)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CLIENT_ACTION_ID_PATTERN = _REQUEST_ID_PATTERN
_runtime_logger = logging.getLogger("probeinterview.runtime")


def create_app(
    settings: Settings | None = None,
    readiness_checks: Mapping[str, Callable[[], None]] | None = None,
    telemetry_span_exporter: SpanExporter | None = None,
) -> FastAPI:
    """Create the API process after validating runtime configuration."""

    resolved_settings = settings or Settings()
    telemetry = initialize_telemetry(
        resolved_settings,
        service_name=API_SERVICE_NAME,
        span_exporter=telemetry_span_exporter,
    )
    configure_logging(service_resource=telemetry.resource)
    resolved_readiness_checks = (
        dict(readiness_checks)
        if readiness_checks is not None
        else build_readiness_checks(resolved_settings)
    )
    app = FastAPI(title="ProbeInterview API")
    app.state.settings = resolved_settings
    app.state.readiness_checks = resolved_readiness_checks
    app.state.telemetry = telemetry

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        candidate = request.headers.get("X-Request-ID", "")
        request_id = candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())
        client_action_candidate = request.headers.get("X-Client-Action-ID", "")
        client_action_id = (
            client_action_candidate
            if _CLIENT_ACTION_ID_PATTERN.fullmatch(client_action_candidate)
            else None
        )
        request.state.request_id = request_id
        with bind_log_context(
            request_id=request_id,
            client_action_id=client_action_id,
        ):
            try:
                response = await call_next(request)
            except Exception as error:
                safe_error = safe_exception_details(error, error_code="internal_error")
                _runtime_logger.error(
                    "Unhandled application error",
                    extra={
                        "event": "http.request.failed",
                        "summary": "Unhandled application error",
                        "error_code": "internal_error",
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_status": 500,
                        **safe_error,
                    },
                )
                response = problem_response(
                    ProblemDetails(
                        title="Internal Server Error",
                        status=500,
                        detail="An unexpected error occurred.",
                        instance=request.url.path,
                        code="internal_error",
                        request_id=request_id,
                    )
                )
            else:
                _runtime_logger.info(
                    "HTTP request completed",
                    extra={
                        "event": "http.request.completed",
                        "summary": "HTTP request completed",
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_status": response.status_code,
                    },
                )
            response.headers["X-Request-ID"] = request_id
            trace_id = current_trace_id()
            if trace_id is not None:
                response.headers["X-Trace-ID"] = trace_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_problem(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        violations = [
            FieldViolation(
                field=".".join(str(location) for location in item["loc"]),
                message=item["msg"],
                code=item["type"],
            )
            for item in error.errors()
        ]
        return problem_response(
            ProblemDetails(
                title="Validation Error",
                status=422,
                detail="Request validation failed.",
                instance=request.url.path,
                code="validation_error",
                request_id=request.state.request_id,
                errors=violations,
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_problem(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        if error.status_code == 404:
            title = "Not Found"
            detail = "The requested resource was not found."
            code = "not_found"
        else:
            try:
                title = HTTPStatus(error.status_code).phrase
            except ValueError:
                title = "HTTP Error"
            detail = "The request could not be completed."
            code = "http_error"

        return problem_response(
            ProblemDetails(
                title=title,
                status=error.status_code,
                detail=detail,
                instance=request.url.path,
                code=code,
                request_id=request.state.request_id,
            )
        )

    @app.get("/health/live", response_model=HealthResource)
    async def live() -> HealthResource:
        return HealthResource(status="ok")

    @app.get("/health/ready", response_model=ReadinessResource)
    async def ready(request: Request) -> ReadinessResource | JSONResponse:
        unavailable_dependencies: list[str] = []
        checks = readiness_checks_from_state(request.app.state)
        for dependency, check in checks.items():
            try:
                await run_in_threadpool(check)
            except Exception:
                unavailable_dependencies.append(dependency)

        if unavailable_dependencies:
            _runtime_logger.warning(
                "Runtime dependencies unavailable",
                extra={
                    "event": "health.readiness.failed",
                    "summary": "Runtime dependencies unavailable",
                    "error_code": "dependencies_unavailable",
                    "unavailable_dependencies": unavailable_dependencies,
                },
            )
            return problem_response(
                ProblemDetails(
                    title="Service Unavailable",
                    status=503,
                    detail="Required runtime dependencies are unavailable.",
                    instance=request.url.path,
                    code="dependencies_unavailable",
                    request_id=request.state.request_id,
                    unavailable_dependencies=unavailable_dependencies,
                )
            )

        return ReadinessResource(
            status="ready",
            dependencies={dependency: "available" for dependency in checks},
        )

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=telemetry.tracer_provider,
        exclude_spans=["receive", "send"],
    )
    return app


def readiness_checks_from_state(state: State) -> dict[str, ReadinessCheck]:
    """Return the validated readiness check mapping stored at app creation."""

    return dict(state.readiness_checks)


def current_trace_id() -> str | None:
    """Return the active trace ID for diagnostic response headers."""

    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")
