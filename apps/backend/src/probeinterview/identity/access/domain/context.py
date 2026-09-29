"""Authenticated actor information consumed by application services."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Stable application identity independent of the authentication provider."""

    actor_id: UUID
    capabilities: frozenset[str]
