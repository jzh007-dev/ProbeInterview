"""Local actor resolution boundaries."""

from uuid import UUID

import pytest

from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.identity.access.infrastructure.local_actor import build_actor_provider
from probeinterview.platform.foundation.infrastructure.settings import Settings

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")


def test_enabled_local_actor_resolves_configured_context() -> None:
    provider = build_actor_provider(
        make_settings(local_actor_enabled=True, local_actor_id=ACTOR_ID)
    )

    assert provider.resolve() == ActorContext(actor_id=ACTOR_ID, capabilities=frozenset())


def test_disabled_local_actor_resolves_nothing() -> None:
    provider = build_actor_provider(make_settings(local_actor_enabled=False, local_actor_id=None))

    assert provider.resolve() is None


def test_provider_factory_refuses_production_even_if_validation_is_bypassed() -> None:
    settings = Settings.model_construct(
        environment="production",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        local_actor_enabled=True,
        local_actor_id=ACTOR_ID,
    )

    with pytest.raises(ValueError, match="production forbids local actor provider"):
        build_actor_provider(settings)


def make_settings(
    *,
    local_actor_enabled: bool,
    local_actor_id: UUID | None,
) -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        local_actor_enabled=local_actor_enabled,
        local_actor_id=local_actor_id,
        _env_file=None,
    )
