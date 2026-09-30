"""Current actor overview composition invariants."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from probeinterview.candidate.profile.application.contracts import (
    CurrentResumeOverview,
    TargetProfileOverview,
)
from probeinterview.candidate.profile.application.overview import GetProfileOverview
from probeinterview.identity.access.application.queries import IdentityDisplay
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.platform.foundation.application.object_storage import SignedObjectUrl

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
EXPIRES_AT = datetime(2026, 10, 1, 8, 10, tzinfo=UTC)


def test_overview_signs_custom_avatar_and_keeps_object_key_internal() -> None:
    """Custom avatars leave the boundary only as bounded signed URLs."""

    signer = StubAvatarSigner()
    query = GetProfileOverview(
        identity_reader=StubIdentityReader(
            IdentityDisplay(
                id=ACTOR_ID,
                nickname="头像用户",
                avatar_object_key="avatars/0001/display.png",
            )
        ),
        candidate_reader=StubCandidateReader(default_profile=None),
        avatar_signer=signer,
    )

    overview = query.execute(ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()))

    assert overview.avatar_url == "https://display.invalid/signed"
    assert overview.avatar_url_expires_at == EXPIRES_AT
    assert signer.object_keys == ["avatars/0001/display.png"]


def test_overview_without_avatar_or_profile_returns_null_display_fields() -> None:
    """New users get a complete overview with nullable avatar and profile."""

    signer = StubAvatarSigner()
    query = GetProfileOverview(
        identity_reader=StubIdentityReader(
            IdentityDisplay(id=ACTOR_ID, nickname="新用户", avatar_object_key=None)
        ),
        candidate_reader=StubCandidateReader(default_profile=None),
        avatar_signer=signer,
    )

    overview = query.execute(ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()))

    assert overview.nickname == "新用户"
    assert overview.avatar_url is None
    assert overview.avatar_url_expires_at is None
    assert overview.default_target_profile is None
    assert signer.object_keys == []


def test_overview_keeps_explicit_default_profile_and_resume() -> None:
    """Existing display composition survives the nullable-contract rework."""

    profile = TargetProfileOverview(
        id=uuid4(),
        target_role="Platform Engineer",
        relevant_experience_months=48,
    )
    resume = CurrentResumeOverview(
        id=uuid4(),
        original_file_name="resume.pdf",
        media_type="application/pdf",
        size_bytes=1024,
        revision=1,
        uploaded_at=EXPIRES_AT - timedelta(days=1),
        updated_at=EXPIRES_AT - timedelta(days=1),
    )
    query = GetProfileOverview(
        identity_reader=StubIdentityReader(
            IdentityDisplay(id=ACTOR_ID, nickname="老用户", avatar_object_key=None)
        ),
        candidate_reader=StubCandidateReader(default_profile=profile, resume=resume),
        avatar_signer=StubAvatarSigner(),
    )

    overview = query.execute(ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()))

    assert overview.default_target_profile == profile
    assert overview.current_resume == resume


class StubIdentityReader:
    def __init__(self, display: IdentityDisplay | None) -> None:
        self._display = display

    def get_for_actor(self, actor_id: UUID) -> IdentityDisplay | None:
        return self._display


class StubCandidateReader:
    def __init__(
        self,
        *,
        default_profile: TargetProfileOverview | None,
        resume: CurrentResumeOverview | None = None,
    ) -> None:
        self._default_profile = default_profile
        self._resume = resume

    def get_default_profile(self, actor_id: UUID) -> TargetProfileOverview | None:
        return self._default_profile

    def get_current_resume(self, actor_id: UUID) -> CurrentResumeOverview | None:
        return self._resume


class StubAvatarSigner:
    def __init__(self) -> None:
        self.object_keys: list[str] = []

    def sign(self, object_key: str) -> SignedObjectUrl:
        self.object_keys.append(object_key)
        return SignedObjectUrl(url="https://display.invalid/signed", expires_at=EXPIRES_AT)
