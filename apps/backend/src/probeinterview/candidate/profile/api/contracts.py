"""Typed profile overview HTTP resources."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from probeinterview.candidate.profile.application.overview import ProfileOverview


class TargetProfileResource(BaseModel):
    id: UUID
    target_role: str
    relevant_experience_months: int


class CurrentResumeResource(BaseModel):
    id: UUID
    original_file_name: str
    media_type: str
    size_bytes: int
    revision: int
    uploaded_at: datetime
    updated_at: datetime


class ProfileOverviewResource(BaseModel):
    id: UUID
    nickname: str
    avatar_url: str | None
    default_target_profile: TargetProfileResource
    current_resume: CurrentResumeResource | None
    recent_scores: list[object]

    @classmethod
    def from_application(cls, overview: ProfileOverview) -> "ProfileOverviewResource":
        current_resume = overview.current_resume
        return cls(
            id=overview.id,
            nickname=overview.nickname,
            avatar_url=overview.avatar_url,
            default_target_profile=TargetProfileResource(
                id=overview.default_target_profile.id,
                target_role=overview.default_target_profile.target_role,
                relevant_experience_months=(
                    overview.default_target_profile.relevant_experience_months
                ),
            ),
            current_resume=(
                CurrentResumeResource(
                    id=current_resume.id,
                    original_file_name=current_resume.original_file_name,
                    media_type=current_resume.media_type,
                    size_bytes=current_resume.size_bytes,
                    revision=current_resume.revision,
                    uploaded_at=current_resume.uploaded_at,
                    updated_at=current_resume.updated_at,
                )
                if current_resume is not None
                else None
            ),
            recent_scores=[],
        )
