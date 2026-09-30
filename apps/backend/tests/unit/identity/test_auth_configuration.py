"""Authenticator factory behavior for the two authentication modes."""

from uuid import UUID

import pytest

from probeinterview.identity.access.application.authentication import (
    BearerSessionAuthenticator,
)
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.identity.access.infrastructure.authenticators import (
    LocalActorProvider,
    build_actor_authenticator,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")


def test_explicit_local_test_mode_resolves_persisted_actor() -> None:
    capability_reader = StubCapabilityReader(frozenset({"knowledge.submit_public"}))

    authenticator = build_actor_authenticator(
        make_settings(authentication_mode="local_test", local_actor_id=ACTOR_ID),
        capability_reader=capability_reader,
    )

    assert isinstance(authenticator, LocalActorProvider)
    assert authenticator.authenticate(None) == ActorContext(
        actor_id=ACTOR_ID,
        capabilities=frozenset({"knowledge.submit_public"}),
    )
    assert capability_reader.actor_ids == [ACTOR_ID]


def test_wechat_mode_builds_session_authenticator_without_anonymous_fallback() -> None:
    session_store = StubSessionResolver(None)

    authenticator = build_actor_authenticator(
        make_settings(authentication_mode="wechat"),
        capability_reader=StubCapabilityReader(frozenset()),
        session_store=session_store,
    )

    assert isinstance(authenticator, BearerSessionAuthenticator)
    assert authenticator.authenticate(None) is None
    assert session_store.digests == []


def test_authenticator_factory_refuses_local_test_outside_test_if_validation_is_bypassed() -> None:
    settings = Settings.model_construct(
        environment="production",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="local_test",
        local_actor_id=ACTOR_ID,
    )

    with pytest.raises(ValueError, match="local_test authentication requires test environment"):
        build_actor_authenticator(settings)


def test_wechat_mode_requires_session_persistence_when_no_factory_is_given() -> None:
    settings = Settings.model_construct(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
    )

    with pytest.raises(ValueError, match="wechat authentication requires session persistence"):
        build_actor_authenticator(settings)


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": "postgresql+psycopg://probe:probe@db/probe",
        "celery_broker_url": "redis://redis:6379/0",
        "authentication_mode": "wechat",
        "local_actor_id": None,
        "wechat_adapter": "fake",
        "wechat_app_id": "test-app",
    }
    values.update(overrides)
    if values["authentication_mode"] == "local_test":
        values["wechat_app_id"] = None
    return Settings(**values, _env_file=None)


class StubCapabilityReader:
    def __init__(self, capabilities: frozenset[str]) -> None:
        self.capabilities = capabilities
        self.actor_ids: list[UUID] = []

    def get_for_actor(self, actor_id: UUID) -> frozenset[str]:
        self.actor_ids.append(actor_id)
        return self.capabilities


class StubSessionResolver:
    def __init__(self, user_id: UUID | None) -> None:
        self.user_id = user_id
        self.digests: list[str] = []

    def resolve_active(self, token_digest: str, now: object) -> UUID | None:
        self.digests.append(token_digest)
        return self.user_id
