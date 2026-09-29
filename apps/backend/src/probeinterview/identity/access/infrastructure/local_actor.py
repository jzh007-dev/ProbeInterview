"""Configuration-backed actor provider for development and tests."""

from dataclasses import dataclass

from probeinterview.identity.access.application.actors import ActorProvider
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.platform.foundation.infrastructure.settings import Settings


@dataclass(frozen=True, slots=True)
class LocalActorProvider:
    """Return one actor selected by validated process configuration."""

    actor: ActorContext

    def resolve(self) -> ActorContext:
        return self.actor


class NoActorProvider:
    """Provider used when no authentication mechanism is enabled."""

    def resolve(self) -> None:
        return None


def build_actor_provider(settings: Settings) -> ActorProvider:
    """Build a non-production local provider or an unresolved provider."""

    if not settings.local_actor_enabled:
        return NoActorProvider()
    if settings.environment == "production":
        raise ValueError("production forbids local actor provider")
    if settings.local_actor_id is None:
        raise ValueError("local actor requires local_actor_id")
    return LocalActorProvider(
        ActorContext(
            actor_id=settings.local_actor_id,
            capabilities=frozenset(),
        )
    )
