"""Bearer session authentication for protected business APIs."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from probeinterview.identity.access.application.tokens import token_digest
from probeinterview.identity.access.domain.context import ActorContext


class SessionResolver(Protocol):
    """Resolve live bearer sessions from digest-only persistence."""

    def resolve_active(self, token_digest: str, now: datetime) -> UUID | None:
        """Return the user id when the digest maps to a live session."""


class CapabilitySource(Protocol):
    """Identity-owned capability query re-read on every authentication."""

    def get_for_actor(self, actor_id: UUID) -> frozenset[str]: ...


class BearerSessionAuthenticator:
    """Resolve one opaque bearer token into the owning actor context.

    A missing credential resolves to None without touching persistence, so
    malformed or absent headers can never trigger storage lookups. Sessions
    are re-resolved and capabilities re-read on every request, which keeps
    capability changes effective from the next request onward.
    """

    def __init__(
        self,
        *,
        sessions: SessionResolver,
        capabilities: CapabilitySource,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._capabilities = capabilities
        self._clock = clock or (lambda: datetime.now(UTC))

    def authenticate(self, bearer_token: str | None) -> ActorContext | None:
        """Return the session owner or None when the token does not resolve."""

        if bearer_token is None:
            return None
        now = self._clock().astimezone(UTC)
        user_id = self._sessions.resolve_active(token_digest(bearer_token), now)
        if user_id is None:
            return None
        return ActorContext(
            actor_id=user_id,
            capabilities=self._capabilities.get_for_actor(user_id),
        )
