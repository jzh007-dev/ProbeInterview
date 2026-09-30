"""Composition-root wiring for the identity authentication boundary."""

from dataclasses import replace
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from probeinterview.candidate.profile.application.contracts import (
    CandidateOverviewReader,
)
from probeinterview.candidate.profile.infrastructure.queries import (
    SqlAlchemyCandidateOverviewReader,
)
from probeinterview.identity.access.application.exchange import (
    ExchangeSnapshot,
    ExchangeSnapshotReader,
    ExchangeTargetProfile,
    WeChatExchangeService,
)
from probeinterview.identity.access.application.registration import RegistrationService
from probeinterview.identity.access.application.wechat import WeChatIdentityExchange
from probeinterview.identity.access.infrastructure.auth_stores import (
    SqlAlchemyAuthSessionStore,
    SqlAlchemyExchangeSnapshotReader,
    SqlAlchemyRegistrationAttemptStore,
    SqlAlchemyWeChatBindingReader,
)
from probeinterview.identity.access.infrastructure.registration_store import (
    SqlAlchemyRegistrationStore,
)
from probeinterview.platform.foundation.application.object_storage import ObjectStorage
from probeinterview.platform.foundation.infrastructure.settings import Settings


class ComposedExchangeSnapshotReader:
    """Compose identity-owned snapshot fields with the candidate contract."""

    def __init__(
        self,
        identity_snapshots: ExchangeSnapshotReader,
        candidate_reader: CandidateOverviewReader,
    ) -> None:
        self._identity_snapshots = identity_snapshots
        self._candidate_reader = candidate_reader

    def get_snapshot(self, user_id: UUID) -> ExchangeSnapshot | None:
        """Return the full display snapshot for user_id."""

        snapshot = self._identity_snapshots.get_snapshot(user_id)
        if snapshot is None:
            return None
        profile = self._candidate_reader.get_default_profile(user_id)
        if profile is None:
            return snapshot
        return replace(
            snapshot,
            default_target_profile=ExchangeTargetProfile(
                target_role=profile.target_role,
                relevant_experience_months=profile.relevant_experience_months,
            ),
        )


def build_composed_snapshot_reader(
    session_factory: sessionmaker[Session],
) -> ComposedExchangeSnapshotReader:
    """Build the shared identity-plus-candidate snapshot reader."""

    return ComposedExchangeSnapshotReader(
        identity_snapshots=SqlAlchemyExchangeSnapshotReader(session_factory),
        candidate_reader=SqlAlchemyCandidateOverviewReader(session_factory),
    )


def build_wechat_exchange_service(
    settings: Settings,
    session_factory: sessionmaker[Session],
    wechat: WeChatIdentityExchange,
) -> WeChatExchangeService:
    """Wire the exchange service against the configured adapters and stores."""

    return WeChatExchangeService(
        wechat=wechat,
        bindings=SqlAlchemyWeChatBindingReader(session_factory),
        snapshots=build_composed_snapshot_reader(session_factory),
        sessions=SqlAlchemyAuthSessionStore(session_factory),
        attempts=SqlAlchemyRegistrationAttemptStore(session_factory),
        app_id=settings.wechat_app_id or "",
    )


def build_wechat_registration_service(
    session_factory: sessionmaker[Session],
    storage: ObjectStorage,
) -> RegistrationService:
    """Wire the registration service against the stores and shared storage."""

    return RegistrationService(
        registrations=SqlAlchemyRegistrationStore(session_factory),
        snapshots=build_composed_snapshot_reader(session_factory),
        sessions=SqlAlchemyAuthSessionStore(session_factory),
        storage=storage,
    )
