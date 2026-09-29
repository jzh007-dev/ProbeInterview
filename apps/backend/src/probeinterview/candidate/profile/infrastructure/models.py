"""Candidate-profile-owned SQLAlchemy mappings."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from probeinterview.platform.foundation.infrastructure.persistence import Base


class CandidateProfileModel(Base):
    """One candidate's target interview role and relevant experience."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint(
            "relevant_experience_months >= 0",
            name="ck_candidate_profiles_experience_non_negative",
        ),
        Index(
            "uq_candidate_profiles_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default IS TRUE"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_role: Mapped[str] = mapped_column(String(200), nullable=False)
    relevant_experience_months: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserResumeModel(Base):
    """Storage-neutral metadata for one user's current resume."""

    __tablename__ = "user_resume"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_resume_user_id"),
        UniqueConstraint(
            "storage_object_key",
            name="uq_user_resume_storage_object_key",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_user_resume_size_non_negative"),
        CheckConstraint(
            "length(content_sha256) = 64",
            name="ck_user_resume_content_sha256_length",
        ),
        CheckConstraint(
            "length(btrim(storage_object_key)) > 0",
            name="ck_user_resume_storage_object_key_non_blank",
        ),
        CheckConstraint("revision > 0", name="ck_user_resume_revision_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
