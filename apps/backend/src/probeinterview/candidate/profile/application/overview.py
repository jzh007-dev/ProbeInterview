"""Current actor profile overview orchestration."""

from dataclasses import dataclass
from uuid import UUID

from probeinterview.candidate.profile.application.contracts import (
    CandidateOverviewReader,
    CurrentResumeOverview,
    TargetProfileOverview,
)
from probeinterview.identity.access.application.queries import (
    IdentityDisplay,
    IdentityDisplayReader,
)
from probeinterview.identity.access.domain.context import ActorContext


class CurrentActorNotFound(Exception):
    """Raised when configured actor data is missing from persistence."""


class ProfileOverviewIncomplete(Exception):
    """Raised when the actor has no explicit default target profile."""


@dataclass(frozen=True, slots=True)
class ProfileOverview:
    id: UUID
    nickname: str
    avatar_url: str | None
    default_target_profile: TargetProfileOverview
    current_resume: CurrentResumeOverview | None
    recent_scores: tuple[()]


class GetProfileOverview:
    """Compose the owner-scoped overview through module contracts."""

    def __init__(
        self,
        identity_reader: IdentityDisplayReader,
        candidate_reader: CandidateOverviewReader,
    ) -> None:
        self._identity_reader = identity_reader
        self._candidate_reader = candidate_reader

    def execute(self, actor: ActorContext) -> ProfileOverview:
        identity = self._identity_reader.get_for_actor(actor.actor_id)
        if identity is None:
            raise CurrentActorNotFound
        default_profile = self._candidate_reader.get_default_profile(actor.actor_id)
        if default_profile is None:
            raise ProfileOverviewIncomplete
        return self._compose(
            identity,
            default_profile,
            self._candidate_reader.get_current_resume(actor.actor_id),
        )

    @staticmethod
    def _compose(
        identity: IdentityDisplay,
        default_profile: TargetProfileOverview,
        current_resume: CurrentResumeOverview | None,
    ) -> ProfileOverview:
        return ProfileOverview(
            id=identity.id,
            nickname=identity.nickname,
            avatar_url=identity.avatar_object_key,
            default_target_profile=default_profile,
            current_resume=current_resume,
            recent_scores=(),
        )
