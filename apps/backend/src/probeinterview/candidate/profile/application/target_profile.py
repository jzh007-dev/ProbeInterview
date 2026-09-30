"""Default target profile creation and modification."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from probeinterview.candidate.profile.application.contracts import (
    TargetProfileOverview,
)
from probeinterview.identity.access.domain.context import ActorContext

TARGET_ROLE_MAX_LENGTH = 200


class TargetProfileFieldInvalid(Exception):
    """One target profile field violated its display-safe rules."""

    def __init__(self, *, field: str, message: str, code: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


def validate_target_role(target_role: str) -> str:
    """Return the trimmed display-safe target role or raise a field error."""

    normalized = target_role.strip()
    if not normalized:
        raise TargetProfileFieldInvalid(
            field="target_role",
            message="A non-empty target role is required.",
            code="invalid_target_role",
        )
    if len(normalized) > TARGET_ROLE_MAX_LENGTH:
        raise TargetProfileFieldInvalid(
            field="target_role",
            message=f"The target role must contain at most {TARGET_ROLE_MAX_LENGTH} characters.",
            code="invalid_target_role",
        )
    if any(_is_control(char) for char in normalized):
        raise TargetProfileFieldInvalid(
            field="target_role",
            message="The target role must not contain control characters.",
            code="invalid_target_role",
        )
    return normalized


def _is_control(char: str) -> bool:
    return "\x00" <= char <= "\x1f" or "\x7f" <= char <= "\x9f"


@dataclass(frozen=True, slots=True)
class TargetProfileWrite:
    """One validated default target profile write."""

    target_role: str
    relevant_experience_months: int


class DefaultTargetProfileStore(Protocol):
    """Persist the actor-owned default target profile."""

    def upsert_default(self, actor_id: UUID, write: TargetProfileWrite) -> TargetProfileOverview:
        """Create or update the actor's default profile and return it."""

        ...


class SetDefaultTargetProfile:
    """Create or update the calling actor's default target profile.

    The actor scope comes exclusively from the authenticated context; no
    request-supplied identifier can redirect the write or the read-back.
    Nickname and avatar belong to identity and are never touched here.
    """

    def __init__(self, store: DefaultTargetProfileStore) -> None:
        self._store = store

    def execute(
        self,
        actor: ActorContext,
        target_role: str,
        relevant_experience_months: int,
    ) -> TargetProfileOverview:
        """Validate and persist one default target profile write."""

        safe_role = validate_target_role(target_role)
        return self._store.upsert_default(
            actor.actor_id,
            TargetProfileWrite(
                target_role=safe_role,
                relevant_experience_months=relevant_experience_months,
            ),
        )
