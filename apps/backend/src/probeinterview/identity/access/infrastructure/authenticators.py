"""Configuration-backed and session-backed actor authenticators."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from probeinterview.identity.access.application.actors import ActorAuthenticator
from probeinterview.identity.access.application.authentication import (
    BearerSessionAuthenticator,
    SessionResolver,
)
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.identity.access.infrastructure.auth_stores import (
    SqlAlchemyAuthSessionStore,
)
from probeinterview.identity.access.infrastructure.queries import (
    SqlAlchemyCapabilityReader,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings


class CapabilityReader(Protocol):
    """Identity-owned capability query used by every authenticator."""

    def get_for_actor(self, actor_id: UUID) -> frozenset[str]: ...


@dataclass(frozen=True, slots=True)
class LocalActorProvider:
    """Test-only authenticator that ignores credentials entirely."""

    actor_id: UUID
    capability_reader: CapabilityReader

    def authenticate(self, bearer_token: str | None) -> ActorContext:
        return ActorContext(
            actor_id=self.actor_id,
            capabilities=self.capability_reader.get_for_actor(self.actor_id),
        )


def build_actor_authenticator(
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    *,
    capability_reader: CapabilityReader | None = None,
    session_store: SessionResolver | None = None,
) -> ActorAuthenticator:
    """Build the configured authenticator without any anonymous fallback."""

    if settings.authentication_mode != "wechat":
        if settings.environment != "test":
            raise ValueError("local_test authentication requires test environment")
        if settings.local_actor_id is None:
            raise ValueError("local_test authentication requires local_actor_id")
        resolved_reader = capability_reader
        if resolved_reader is None:
            if session_factory is None:
                raise ValueError("local actor requires capability persistence")
            resolved_reader = SqlAlchemyCapabilityReader(session_factory)
        return LocalActorProvider(
            actor_id=settings.local_actor_id,
            capability_reader=resolved_reader,
        )

    resolved_store = session_store
    if resolved_store is None:
        if session_factory is None:
            raise ValueError("wechat authentication requires session persistence")
        resolved_store = SqlAlchemyAuthSessionStore(session_factory)
    resolved_reader = capability_reader
    if resolved_reader is None:
        if session_factory is None:
            raise ValueError("wechat authentication requires capability persistence")
        resolved_reader = SqlAlchemyCapabilityReader(session_factory)
    return BearerSessionAuthenticator(
        sessions=resolved_store,
        capabilities=resolved_reader,
    )
