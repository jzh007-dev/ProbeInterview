from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.testclient import TestClient

from probeinterview.entrypoints import api, database_initializer, worker
from probeinterview.identity.access.api.dependencies import current_actor
from probeinterview.identity.access.application.authentication import (
    BearerSessionAuthenticator,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

WECHAT_APP_SETTINGS = Settings(
    environment="test",
    database_url="postgresql+psycopg://probe:probe@db/probe",
    celery_broker_url="redis://redis:6379/0",
    authentication_mode="wechat",
    wechat_adapter="fake",
    wechat_app_id="entrypoint-test",
    foundation_probe_enabled=False,
    _env_file=None,
)


def test_api_factory_validates_settings_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROBEINTERVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("PROBEINTERVIEW_CELERY_BROKER_URL", raising=False)
    create_app = getattr(api, "create_app", None)
    assert create_app is not None, "API startup factory has not been implemented"

    with pytest.raises(ValidationError):
        create_app()


def test_worker_factory_validates_settings_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROBEINTERVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("PROBEINTERVIEW_CELERY_BROKER_URL", raising=False)
    create_celery_app = getattr(worker, "create_celery_app", None)
    assert create_celery_app is not None, "worker startup factory has not been implemented"

    with pytest.raises(ValidationError):
        create_celery_app()


def test_database_initializer_migrates_before_optional_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    config = type("Config", (), {"attributes": {}})()
    engine = type("Engine", (), {"dispose": lambda self: events.append("dispose")})()
    monkeypatch.setattr(database_initializer, "Config", lambda _: config)
    monkeypatch.setattr(
        database_initializer.command,
        "upgrade",
        lambda received_config, revision: events.append(
            ("upgrade", received_config.attributes["database_url"], revision)
        ),
    )
    monkeypatch.setattr(
        database_initializer,
        "create_engine",
        lambda database_url: events.append(("engine", database_url)) or engine,
    )
    monkeypatch.setattr(
        database_initializer,
        "seed_demo_profile",
        lambda received_engine: events.append(("seed", received_engine)),
    )

    database_initializer.initialize_database(make_initializer_settings(seed=True))

    assert events == [
        ("upgrade", "postgresql+psycopg://probe:probe@db/probe", "head"),
        ("engine", "postgresql+psycopg://probe:probe@db/probe"),
        ("seed", engine),
        "dispose",
    ]


def test_database_initializer_skips_demo_seed_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrades: list[str] = []
    config = type("Config", (), {"attributes": {}})()
    monkeypatch.setattr(database_initializer, "Config", lambda _: config)
    monkeypatch.setattr(
        database_initializer.command,
        "upgrade",
        lambda _config, revision: upgrades.append(revision),
    )
    monkeypatch.setattr(
        database_initializer,
        "create_engine",
        lambda _database_url: pytest.fail("seed engine must not be created"),
    )

    database_initializer.initialize_database(make_initializer_settings(seed=False))

    assert upgrades == ["head"]


def make_initializer_settings(*, seed: bool) -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="entrypoint-test",
        demo_profile_seed_enabled=seed,
        _env_file=None,
    )


def test_openapi_route_inventory_keeps_only_health_and_bootstrap_public() -> None:
    """Only the health pair and the three bootstrap routes stay unauthenticated."""

    app = api.create_app(settings=WECHAT_APP_SETTINGS, readiness_checks={})

    api_routes = list(iter_api_routes(app))
    public_paths = {
        route.path
        for route in api_routes
        if route.path.startswith("/api/v1") and not requires_authentication(route)
    }
    assert public_paths == {
        "/api/v1/auth/wechat/exchanges",
        "/api/v1/auth/wechat/registrations",
        "/api/v1/auth/wechat/avatar-registrations",
    }
    protected_paths = {
        route.path
        for route in api_routes
        if route.path.startswith("/api/v1") and requires_authentication(route)
    }
    assert "/api/v1/me/overview" in protected_paths
    assert "/api/v1/me/knowledge-sources" in protected_paths
    health_paths = {route.path for route in api_routes if route.path.startswith("/health")}
    assert health_paths == {"/health/live", "/health/ready"}
    for route in api_routes:
        if route.path in health_paths:
            assert not requires_authentication(route)


def test_newly_mounted_business_router_is_protected_at_the_mount_point() -> None:
    """A future business route is 401-guarded without declaring auth itself.

    The probe handler declares no authentication dependency, so the 401 can
    only come from the structured mount-point boundary.
    """

    app = api.create_app(settings=WECHAT_APP_SETTINGS, readiness_checks={})
    probe = APIRouter()

    @probe.get("/api/v1/future/resources")
    def list_future_resources() -> dict[str, str]:
        return {"status": "ok"}

    api.mount_business_routers(app, probe)
    app.state.actor_authenticator = BearerSessionAuthenticator(
        sessions=_StubSessionResolver(None),
        capabilities=_StubCapabilityReader(),
    )
    client = TestClient(app)

    response = client.get("/api/v1/future/resources")
    authenticated_probe = client.get(
        "/api/v1/future/resources",
        headers={"Authorization": "Bearer not-a-known-session-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    assert authenticated_probe.status_code == 401


def test_authentication_failure_invokes_no_business_repository_or_storage() -> None:
    """Rejected requests must never reach business services or object storage."""

    app = api.create_app(settings=WECHAT_APP_SETTINGS, readiness_checks={})
    business_calls: list[str] = []
    app.state.profile_overview_query = _RecordingOverviewQuery(business_calls)
    app.state.knowledge_source_service = _RecordingKnowledgeService(business_calls)
    app.state.actor_authenticator = BearerSessionAuthenticator(
        sessions=_StubSessionResolver(None),
        capabilities=_StubCapabilityReader(),
    )
    client = TestClient(app)

    for headers in (
        {},
        {"Authorization": ""},
        {"Authorization": "Basic Zm9vOmJhcg=="},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer not-a-known-session-token"},
    ):
        response = client.get("/api/v1/me/overview", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == "authentication_required"

    assert business_calls == []
    assert app.state.object_storage.calls == []


def test_authentication_failure_response_and_logs_never_contain_the_token() -> None:
    """The presented bearer token stays out of the problem body and the logs."""

    import logging as logging_module

    from probeinterview.platform.foundation.infrastructure.logging import (
        JsonLogFormatter,
    )

    app = api.create_app(settings=WECHAT_APP_SETTINGS, readiness_checks={})
    app.state.actor_authenticator = BearerSessionAuthenticator(
        sessions=_StubSessionResolver(None),
        capabilities=_StubCapabilityReader(),
    )
    presented_token = "super-secret-presented-token"
    captured: list[str] = []

    class CapturingHandler(logging_module.Handler):
        def emit(self, record: logging_module.LogRecord) -> None:
            captured.append(self.format(record))

    probe_handler = CapturingHandler()
    probe_handler.setFormatter(JsonLogFormatter())
    logging_module.getLogger("probeinterview").addHandler(probe_handler)
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/me/overview",
            headers={"Authorization": f"Bearer {presented_token}"},
        )
    finally:
        logging_module.getLogger("probeinterview").removeHandler(probe_handler)

    assert response.status_code == 401
    assert presented_token not in response.text
    assert captured, "the request must still be logged"
    assert all(presented_token not in line for line in captured)


def requires_authentication(route: APIRoute) -> bool:
    """Return whether the route's dependency tree resolves the current actor."""

    stack = [route.dependant]
    while stack:
        dependant = stack.pop()
        if dependant.call is current_actor:
            return True
        stack.extend(dependant.dependencies)
    return False


def iter_api_routes(app: object) -> Iterator[APIRoute]:
    """Yield every API route, descending into lazily included routers."""

    routes: object = getattr(app, "routes", app)
    for route in routes:  # type: ignore[union-attr]
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from iter_api_routes(route.original_router)


class _RecordingOverviewQuery:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def execute(self, actor: object) -> None:
        self._calls.append("overview")


class _RecordingKnowledgeService:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def upload(self, **kwargs: object) -> None:
        self._calls.append("knowledge.upload")

    def list_for_actor(self, actor: object) -> None:
        self._calls.append("knowledge.list")


class _StubSessionResolver:
    def __init__(self, user_id: object) -> None:
        self._user_id = user_id

    def resolve_active(self, token_digest: str, now: object) -> object:
        return self._user_id


class _StubCapabilityReader:
    def get_for_actor(self, actor_id: object) -> frozenset[str]:
        return frozenset()
