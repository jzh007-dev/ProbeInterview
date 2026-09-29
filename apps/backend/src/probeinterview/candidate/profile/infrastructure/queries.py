"""SQLAlchemy candidate overview query adapter."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.candidate.profile.application.contracts import (
    CurrentResumeOverview,
    TargetProfileOverview,
)
from probeinterview.candidate.profile.infrastructure.models import (
    CandidateProfileModel,
    UserResumeModel,
)


class SqlAlchemyCandidateOverviewReader:
    """Apply actor owner scope in every candidate profile query."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_default_profile(self, actor_id: UUID) -> TargetProfileOverview | None:
        with self._session_factory() as session:
            profile = session.scalar(
                select(CandidateProfileModel).where(
                    CandidateProfileModel.user_id == actor_id,
                    CandidateProfileModel.is_default.is_(True),
                )
            )
        if profile is None:
            return None
        return TargetProfileOverview(
            id=profile.id,
            target_role=profile.target_role,
            relevant_experience_months=profile.relevant_experience_months,
        )

    def get_current_resume(self, actor_id: UUID) -> CurrentResumeOverview | None:
        with self._session_factory() as session:
            resume = session.scalar(
                select(UserResumeModel).where(UserResumeModel.user_id == actor_id)
            )
        if resume is None:
            return None
        return CurrentResumeOverview(
            id=resume.id,
            original_file_name=resume.original_file_name,
            media_type=resume.media_type,
            size_bytes=resume.size_bytes,
            revision=resume.revision,
            uploaded_at=resume.uploaded_at,
            updated_at=resume.updated_at,
        )
