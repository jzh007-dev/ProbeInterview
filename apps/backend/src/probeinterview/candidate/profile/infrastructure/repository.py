"""SQLAlchemy persistence for the actor-owned default target profile."""

from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.candidate.profile.application.contracts import (
    TargetProfileOverview,
)
from probeinterview.candidate.profile.application.target_profile import (
    TargetProfileWrite,
)
from probeinterview.candidate.profile.infrastructure.models import (
    CandidateProfileModel,
)


class SqlAlchemyDefaultTargetProfileStore:
    """Upsert one default target profile per actor under an actor-scoped lock."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def upsert_default(
        self,
        actor_id: UUID,
        write: TargetProfileWrite,
    ) -> TargetProfileOverview:
        """Create or update the actor's default profile and return it.

        The transaction-scoped advisory lock serializes an actor's first
        concurrent write so the create path can never race; the partial
        unique index on ``is_default`` remains the integrity backstop.
        """

        with self._session_factory() as session, session.begin():
            session.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:lock_scope, 0))"),
                {"lock_scope": f"candidate-default-profile:{actor_id}"},
            )
            profile = session.scalar(
                select(CandidateProfileModel)
                .where(
                    CandidateProfileModel.user_id == actor_id,
                    CandidateProfileModel.is_default.is_(True),
                )
                .with_for_update()
            )
            if profile is None:
                profile = CandidateProfileModel(
                    id=uuid4(),
                    user_id=actor_id,
                    target_role=write.target_role,
                    relevant_experience_months=write.relevant_experience_months,
                    is_default=True,
                )
                session.add(profile)
                session.flush()
            else:
                profile.target_role = write.target_role
                profile.relevant_experience_months = write.relevant_experience_months
            return TargetProfileOverview(
                id=profile.id,
                target_role=profile.target_role,
                relevant_experience_months=profile.relevant_experience_months,
            )
