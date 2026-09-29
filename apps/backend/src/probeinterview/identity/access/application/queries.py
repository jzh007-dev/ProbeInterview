"""Display-safe identity query contract."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IdentityDisplay:
    """Account fields safe to expose in the current user's overview."""

    id: UUID
    nickname: str
    avatar_url: str


class IdentityDisplayReader(Protocol):
    """Read display data only after applying the actor owner scope."""

    def get_for_actor(self, actor_id: UUID) -> IdentityDisplay | None:
        """Return display data belonging to actor_id, if it exists."""
