"""Current actor profile overview orchestration."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from probeinterview.candidate.profile.application.contracts import (
    AvatarUrlSigner,
    CandidateOverviewReader,
    CurrentResumeOverview,
    TargetProfileOverview,
)
from probeinterview.identity.access.application.queries import (
    IdentityDisplayReader,
)
from probeinterview.identity.access.domain.context import ActorContext


@dataclass(frozen=True, slots=True)
class ProfileOverview:
    id: UUID
    nickname: str
    avatar_url: str | None
    avatar_url_expires_at: datetime | None
    default_target_profile: TargetProfileOverview | None
    current_resume: CurrentResumeOverview | None
    recent_scores: tuple[()]


class GetProfileOverview:
    """Compose the owner-scoped overview through module contracts.

    Every display field is nullable by contract: new users own neither a
    custom avatar nor a default target profile yet. Object keys never leave
    this boundary; custom avatars become short-lived signed display URLs.
    """

    def __init__(
        self,
        identity_reader: IdentityDisplayReader,
        candidate_reader: CandidateOverviewReader,
        avatar_signer: AvatarUrlSigner,
    ) -> None:
        self._identity_reader = identity_reader
        self._candidate_reader = candidate_reader
        self._avatar_signer = avatar_signer

    def execute(self, actor: ActorContext) -> ProfileOverview:
        # Both authenticators guarantee the account row exists: sessions
        # resolve through a RESTRICT foreign key, so a missing identity here
        # would be an integrity violation surfaced as an internal error.
        identity = self._identity_reader.get_for_actor(actor.actor_id)
        if identity is None:
            raise ValueError("authenticated actor has no account record")
        signed_avatar = (
            self._avatar_signer.sign(identity.avatar_object_key)
            if identity.avatar_object_key is not None
            else None
        )
        return ProfileOverview(
            id=identity.id,
            nickname=identity.nickname,
            avatar_url=signed_avatar.url if signed_avatar is not None else None,
            avatar_url_expires_at=(signed_avatar.expires_at if signed_avatar is not None else None),
            default_target_profile=self._candidate_reader.get_default_profile(actor.actor_id),
            current_resume=self._candidate_reader.get_current_resume(actor.actor_id),
            recent_scores=(),
        )
