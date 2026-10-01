"""Knowledge-source SQLAlchemy mappings."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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

DEFAULT_DAILY_SUCCESS_LIMIT = 2
DEFAULT_EFFECTIVE_SOURCE_LIMIT = 100
DEFAULT_QUOTA_TIMEZONE = "Asia/Shanghai"


class KnowledgeUploadPolicyModel(Base):
    """Database-backed per-user admission policy."""

    __tablename__ = "knowledge_upload_policies"
    __table_args__ = (
        CheckConstraint(
            "daily_success_limit > 0",
            name="ck_knowledge_upload_policies_daily_positive",
        ),
        CheckConstraint(
            "effective_source_limit > 0",
            name="ck_knowledge_upload_policies_effective_positive",
        ),
        CheckConstraint(
            "quota_timezone = 'Asia/Shanghai'",
            name="ck_knowledge_upload_policies_timezone",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    daily_success_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DAILY_SUCCESS_LIMIT
    )
    effective_source_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_EFFECTIVE_SOURCE_LIMIT
    )
    quota_timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_QUOTA_TIMEZONE,
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


class KnowledgeSourceModel(Base):
    """Owner-scoped upload command and durable source identity."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint("scope in ('PRIVATE', 'PUBLIC')", name="ck_knowledge_sources_scope"),
        CheckConstraint(
            "ingestion_status in ('UPLOADING', 'STORED', 'FAILED')",
            name="ck_knowledge_sources_ingestion_status",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_knowledge_sources_owner_idempotency",
        ),
        UniqueConstraint(
            "id",
            "current_version_id",
            name="uq_knowledge_sources_id_current_version",
        ),
        ForeignKeyConstraint(
            ["id", "current_version_id"],
            ["knowledge_source_versions.source_id", "knowledge_source_versions.id"],
            name="fk_knowledge_sources_current_version_same_source",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        Index(
            "uq_knowledge_sources_owner_scope_sha_effective",
            "owner_user_id",
            "scope",
            "content_sha256",
            unique=True,
            postgresql_where=text("ingestion_status in ('UPLOADING', 'STORED')"),
        ),
        Index(
            "ix_knowledge_sources_owner_stored_order",
            "owner_user_id",
            text("stored_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_knowledge_sources_owner_quota_day_status",
            "owner_user_id",
            "quota_day",
            "ingestion_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    creator_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(16), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    quota_day: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class KnowledgeSourceVersionModel(Base):
    """Immutable original-file metadata for one source version."""

    __tablename__ = "knowledge_source_versions"
    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_knowledge_source_versions_number_positive",
        ),
        CheckConstraint(
            "byte_size >= 0",
            name="ck_knowledge_source_versions_byte_size_non_negative",
        ),
        CheckConstraint(
            "storage_status in ('UPLOADING', 'STORED', 'FAILED')",
            name="ck_knowledge_source_versions_storage_status",
        ),
        UniqueConstraint(
            "source_id",
            "version_number",
            name="uq_knowledge_source_versions_source_number",
        ),
        UniqueConstraint(
            "source_id",
            "id",
            name="uq_knowledge_source_versions_source_id",
        ),
        UniqueConstraint("object_key", name="uq_knowledge_source_versions_object_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_status: Mapped[str] = mapped_column(String(16), nullable=False)
    processing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
