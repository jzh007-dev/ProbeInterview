"""Configuration-backed actor provider for development and tests."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from probeinterview.identity.access.application.actors import ActorProvider
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.identity.access.infrastructure.queries import SqlAlchemyCapabilityReader
from probeinterview.platform.foundation.infrastructure.settings import Settings


class CapabilityReader(Protocol):
    """Identity-owned capability query used by local authentication."""

    def get_for_actor(self, actor_id: UUID) -> frozenset[str]: ...


@dataclass(frozen=True, slots=True)
class LocalActorProvider:
    """Return one actor selected by validated process configuration."""

    actor_id: UUID
    capability_reader: CapabilityReader

    def resolve(self) -> ActorContext:
        return ActorContext(
            actor_id=self.actor_id,
            capabilities=self.capability_reader.get_for_actor(self.actor_id),
        )


class NoActorProvider:
    """Provider used when no authentication mechanism is enabled."""

    def resolve(self) -> None:
        return None


def build_actor_provider(
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    *,
    capability_reader: CapabilityReader | None = None,
) -> ActorProvider:
    """Build a non-production local provider or an unresolved provider."""

    if settings.authentication_mode != "local_test":
        return NoActorProvider()
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
