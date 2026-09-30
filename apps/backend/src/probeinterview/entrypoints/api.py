"""FastAPI process entrypoint."""

import logging
import re
from collections.abc import Callable, Mapping
from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import State
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from probeinterview.candidate.profile.api.router import router as profile_router
from probeinterview.candidate.profile.application.overview import (
    CurrentActorNotFound,
    GetProfileOverview,
    ProfileOverviewIncomplete,
)
from probeinterview.candidate.profile.infrastructure.queries import (
    SqlAlchemyCandidateOverviewReader,
)
from probeinterview.entrypoints.identity_wiring import (
    build_wechat_exchange_service,
    build_wechat_registration_service,
)
from probeinterview.identity.access.api.dependencies import CurrentActorUnavailable
from probeinterview.identity.access.api.router import router as wechat_auth_router
from probeinterview.identity.access.application.registration import (
    RegistrationFieldInvalid,
    RegistrationStorageUnavailable,
    RegistrationTokenInvalid,
)
from probeinterview.identity.access.application.wechat import (
    WeChatCodeExchangeFailed,
    WeChatServiceUnavailable,
)
from probeinterview.identity.access.infrastructure.local_actor import build_actor_provider
from probeinterview.identity.access.infrastructure.queries import (
    SqlAlchemyIdentityDisplayReader,
)
from probeinterview.identity.access.infrastructure.wechat_adapters import (
    build_wechat_exchange,
)
from probeinterview.knowledge.source.api.router import router as knowledge_source_router
from probeinterview.knowledge.source.application.errors import KnowledgeSourceError
from probeinterview.knowledge.source.application.service import KnowledgeSourceService
from probeinterview.knowledge.source.infrastructure.repository import (
    SqlAlchemyKnowledgeSourceRepository,
)
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
)
from probeinterview.platform.foundation.infrastructure.object_storage import build_object_storage
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)
from probeinterview.platform.foundation.infrastructure.readiness import (
    ReadinessCheck,
    build_readiness_checks,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_runtime_logger = logging.getLogger("probeinterview.runtime")


def create_app(
    settings: Settings | None = None,
    readiness_checks: Mapping[str, Callable[[], None]] | None = None,
) -> FastAPI:
    """Create the API process after validating runtime configuration."""

    resolved_settings = settings or Settings()
    configure_logging()
    resolved_readiness_checks = (
        dict(readiness_checks)
        if readiness_checks is not None
        else build_readiness_checks(resolved_settings)
    )
    app = FastAPI(title="ProbeInterview API")
    app.state.settings = resolved_settings
    app.state.readiness_checks = resolved_readiness_checks
    persistence_engine = create_engine(resolved_settings.database_url)
    session_factory = create_session_factory(persistence_engine)
    app.state.actor_provider = build_actor_provider(resolved_settings, session_factory)
    app.state.persistence_engine = persistence_engine
    app.state.profile_overview_query = GetProfileOverview(
        identity_reader=SqlAlchemyIdentityDisplayReader(session_factory),
        candidate_reader=SqlAlchemyCandidateOverviewReader(session_factory),
    )
    app.state.object_storage = build_object_storage(resolved_settings)
    app.state.knowledge_source_service = KnowledgeSourceService(
        repository=SqlAlchemyKnowledgeSourceRepository(session_factory),
        storage=app.state.object_storage,
    )
    app.include_router(profile_router)
    app.include_router(knowledge_source_router)
    app.include_router(wechat_auth_router)
    app.state.wechat_exchange_service = build_wechat_exchange_service(
        resolved_settings,
        session_factory,
        build_wechat_exchange(resolved_settings),
    )
    app.state.wechat_registration_service = build_wechat_registration_service(
        session_factory,
        app.state.object_storage,
    )

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        candidate = request.headers.get("X-Request-ID", "")
        request_id = candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())
        request.state.request_id = request_id
        with bind_log_context(request_id=request_id, trace_id=request_id):
            try:
                response = await call_next(request)
            except Exception as error:
                _runtime_logger.error(
                    "Unhandled application error",
                    extra={
                        "event": "http.request.failed",
                        "summary": "Unhandled application error",
                        "error_code": "internal_error",
                        "exception_type": type(error).__name__,
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_status": 500,
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

    @app.exception_handler(CurrentActorUnavailable)
    async def actor_required_problem(
        request: Request,
        _error: CurrentActorUnavailable,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Unauthorized",
                status=401,
                detail="A current actor is required.",
                instance=request.url.path,
                code="actor_required",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(WeChatCodeExchangeFailed)
    async def wechat_code_exchange_failed_problem(
        request: Request,
        _error: WeChatCodeExchangeFailed,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="WeChat Code Exchange Failed",
                status=400,
                detail="The WeChat login code is invalid, expired, or already used.",
                instance=request.url.path,
                code="wechat_code_exchange_failed",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(WeChatServiceUnavailable)
    async def wechat_service_unavailable_problem(
        request: Request,
        _error: WeChatServiceUnavailable,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="WeChat Service Unavailable",
                status=503,
                detail="The WeChat identity service is temporarily unavailable.",
                instance=request.url.path,
                code="wechat_service_unavailable",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(RegistrationTokenInvalid)
    async def registration_token_invalid_problem(
        request: Request,
        _error: RegistrationTokenInvalid,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Registration Token Invalid",
                status=401,
                detail="The registration credential is unknown, expired, or already used.",
                instance=request.url.path,
                code="registration_token_invalid",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(RegistrationFieldInvalid)
    async def registration_field_invalid_problem(
        request: Request,
        error: RegistrationFieldInvalid,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Registration Validation Error",
                status=422,
                detail="The registration request contains invalid fields.",
                instance=request.url.path,
                code=error.code,
                request_id=request.state.request_id,
                errors=[
                    FieldViolation(
                        field=error.field,
                        message=error.message,
                        code=error.code,
                    )
                ],
            )
        )

    @app.exception_handler(RegistrationStorageUnavailable)
    async def registration_storage_unavailable_problem(
        request: Request,
        _error: RegistrationStorageUnavailable,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Storage Unavailable",
                status=503,
                detail="Private object storage is temporarily unavailable.",
                instance=request.url.path,
                code="storage_unavailable",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(CurrentActorNotFound)
    async def actor_not_found_problem(
        request: Request,
        _error: CurrentActorNotFound,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Not Found",
                status=404,
                detail="The configured actor was not found.",
                instance=request.url.path,
                code="actor_not_found",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(ProfileOverviewIncomplete)
    async def incomplete_profile_problem(
        request: Request,
        _error: ProfileOverviewIncomplete,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title="Profile Overview Incomplete",
                status=409,
                detail="The current actor has no default target profile.",
                instance=request.url.path,
                code="profile_overview_incomplete",
                request_id=request.state.request_id,
            )
        )

    @app.exception_handler(KnowledgeSourceError)
    async def knowledge_source_problem(
        request: Request,
        error: KnowledgeSourceError,
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                title=error.title,
                status=error.status,
                detail=error.detail,
                instance=request.url.path,
                code=error.code,
                request_id=request.state.request_id,
                errors=[
                    FieldViolation(
                        field=item.field,
                        message=item.message,
                        code=item.code,
                    )
                    for item in error.errors
                ]
                or None,
                quota=(
                    {
                        "timezone": error.quota.timezone,
                        "daily_limit": error.quota.daily_limit,
                        "daily_used": error.quota.daily_used,
                        "effective_source_limit": error.quota.effective_source_limit,
                        "effective_source_count": error.quota.effective_source_count,
                    }
                    if error.quota is not None
                    else None
                ),
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

    return app


def readiness_checks_from_state(state: State) -> dict[str, ReadinessCheck]:
    """Return the validated readiness check mapping stored at app creation."""

    return dict(state.readiness_checks)
