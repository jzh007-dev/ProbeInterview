"""Actor provider application boundary."""

from typing import Protocol

from probeinterview.identity.access.domain.context import ActorContext


class ActorProvider(Protocol):
    """Resolve the current process-configured actor, when one exists."""

    def resolve(self) -> ActorContext | None:
        """Return the actor or None when this provider cannot authenticate."""
