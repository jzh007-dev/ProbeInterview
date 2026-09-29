"""FastAPI dependency for resolving the current actor."""

from fastapi import Request

from probeinterview.identity.access.application.actors import ActorProvider
from probeinterview.identity.access.domain.context import ActorContext


class CurrentActorUnavailable(Exception):
    """Raised when no configured identity provider resolves an actor."""


def current_actor(request: Request) -> ActorContext:
    """Resolve the current actor without accepting request-controlled IDs."""

    provider: ActorProvider = request.app.state.actor_provider
    actor = provider.resolve()
    if actor is None:
        raise CurrentActorUnavailable
    return actor
