"""Typed candidate overview application contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TargetProfileOverview:
    id: UUID
    target_role: str
    relevant_experience_months: int


@dataclass(frozen=True, slots=True)
class CurrentResumeOverview:
    id: UUID
    original_file_name: str
    media_type: str
    size_bytes: int
    revision: int
    uploaded_at: datetime
    updated_at: datetime


class CandidateOverviewReader(Protocol):
    """Read candidate-owned records after applying actor scope."""

    def get_default_profile(self, actor_id: UUID) -> TargetProfileOverview | None:
        """Return only the explicitly marked default profile."""

    def get_current_resume(self, actor_id: UUID) -> CurrentResumeOverview | None:
        """Return display-safe current resume metadata."""
