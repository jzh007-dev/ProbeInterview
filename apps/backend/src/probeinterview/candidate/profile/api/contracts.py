"""Typed profile overview HTTP resources."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from probeinterview.candidate.profile.application.overview import ProfileOverview


class DefaultTargetProfileRequest(BaseModel):
    """One explicit default target profile write.

    No identifier is accepted: the write targets the authenticated actor's
    single default profile, so forged foreign profile IDs are rejected as
    unknown fields instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(min_length=1, max_length=2000)
    relevant_experience_months: int = Field(ge=0, le=600)


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
    avatar_url_expires_at: datetime | None
    default_target_profile: TargetProfileResource | None
    current_resume: CurrentResumeResource | None
    recent_scores: list[object]

    @classmethod
    def from_application(cls, overview: ProfileOverview) -> "ProfileOverviewResource":
        current_resume = overview.current_resume
        default_profile = overview.default_target_profile
        return cls(
            id=overview.id,
            nickname=overview.nickname,
            avatar_url=overview.avatar_url,
            avatar_url_expires_at=overview.avatar_url_expires_at,
            default_target_profile=(
                TargetProfileResource(
                    id=default_profile.id,
                    target_role=default_profile.target_role,
                    relevant_experience_months=default_profile.relevant_experience_months,
                )
                if default_profile is not None
                else None
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
