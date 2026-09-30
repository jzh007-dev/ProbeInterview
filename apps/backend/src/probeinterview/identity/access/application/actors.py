"""Actor authentication boundary."""

from typing import Protocol

from probeinterview.identity.access.domain.context import ActorContext


class ActorAuthenticator(Protocol):
    """Authenticate one request credential into an actor context."""

    def authenticate(self, bearer_token: str | None) -> ActorContext | None:
        """Return the actor, or None when the credential does not resolve."""
