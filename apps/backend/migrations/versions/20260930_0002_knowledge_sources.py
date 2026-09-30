"""Persist knowledge-source upload policy, identity, and version truth.

Revision ID: 20260930_0002
Revises: 20260929_0001
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0002"
down_revision: str | None = "20260929_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create identity capabilities and durable knowledge-source records."""

    op.create_table(
        "user_capabilities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "capability"),
        sa.CheckConstraint(
            "length(btrim(capability)) > 0",
            name="ck_user_capabilities_capability_non_blank",
        ),
    )
    op.create_table(
        "knowledge_upload_policies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "daily_success_limit",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column(
            "effective_source_limit",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column(
            "quota_timezone",
            sa.String(length=64),
            server_default=sa.text("'Asia/Shanghai'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "daily_success_limit > 0",
            name="ck_knowledge_upload_policies_daily_positive",
        ),
        sa.CheckConstraint(
            "effective_source_limit > 0",
            name="ck_knowledge_upload_policies_effective_positive",
        ),
        sa.CheckConstraint(
            "quota_timezone = 'Asia/Shanghai'",
            name="ck_knowledge_upload_policies_timezone",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute(
        """
        insert into knowledge_upload_policies (user_id)
        select id from users
        on conflict (user_id) do nothing
        """
    )
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("creator_user_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("ingestion_status", sa.String(length=16), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("quota_day", sa.Date(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "scope in ('PRIVATE', 'PUBLIC')",
            name="ck_knowledge_sources_scope",
        ),
        sa.CheckConstraint(
            "ingestion_status in ('UPLOADING', 'STORED', 'FAILED')",
            name="ck_knowledge_sources_ingestion_status",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_sources_sha256_hex",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_sources_request_digest_hex",
        ),
        sa.CheckConstraint(
            "length(btrim(idempotency_key)) > 0",
            name="ck_knowledge_sources_idempotency_non_blank",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creator_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_knowledge_sources_owner_idempotency",
        ),
        sa.UniqueConstraint(
            "id",
            "current_version_id",
            name="uq_knowledge_sources_id_current_version",
        ),
    )
    op.create_index(
        "uq_knowledge_sources_owner_scope_sha_effective",
        "knowledge_sources",
        ["owner_user_id", "scope", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("ingestion_status in ('UPLOADING', 'STORED')"),
    )
    op.create_index(
        "ix_knowledge_sources_owner_stored_order",
        "knowledge_sources",
        ["owner_user_id", sa.text("stored_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_knowledge_sources_owner_quota_day_status",
        "knowledge_sources",
        ["owner_user_id", "quota_day", "ingestion_status"],
    )
    op.create_table(
        "knowledge_source_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("storage_status", sa.String(length=16), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_knowledge_source_versions_number_positive",
        ),
        sa.CheckConstraint(
            "byte_size >= 0",
            name="ck_knowledge_source_versions_byte_size_non_negative",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_source_versions_sha256_hex",
        ),
        sa.CheckConstraint(
            "length(btrim(object_key)) > 0",
            name="ck_knowledge_source_versions_object_key_non_blank",
        ),
        sa.CheckConstraint(
            "storage_status in ('UPLOADING', 'STORED', 'FAILED')",
            name="ck_knowledge_source_versions_storage_status",
        ),
        sa.CheckConstraint(
            "processing_status is null or processing_status = 'PENDING_EXTRACTION'",
            name="ck_knowledge_source_versions_processing_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "version_number",
            name="uq_knowledge_source_versions_source_number",
        ),
        sa.UniqueConstraint(
            "source_id",
            "id",
            name="uq_knowledge_source_versions_source_id",
        ),
        sa.UniqueConstraint("object_key", name="uq_knowledge_source_versions_object_key"),
    )
    op.create_foreign_key(
        "fk_knowledge_sources_current_version_same_source",
        "knowledge_sources",
        "knowledge_source_versions",
        ["id", "current_version_id"],
        ["source_id", "id"],
        ondelete="RESTRICT",
        use_alter=True,
    )


def downgrade() -> None:
    """Remove knowledge-source records and identity capability persistence."""

    op.drop_constraint(
        "fk_knowledge_sources_current_version_same_source",
        "knowledge_sources",
        type_="foreignkey",
    )
    op.drop_table("knowledge_source_versions")
    op.drop_index(
        "ix_knowledge_sources_owner_quota_day_status",
        table_name="knowledge_sources",
    )
    op.drop_index(
        "ix_knowledge_sources_owner_stored_order",
        table_name="knowledge_sources",
    )
    op.drop_index(
        "uq_knowledge_sources_owner_scope_sha_effective",
        table_name="knowledge_sources",
        postgresql_where=sa.text("ingestion_status in ('UPLOADING', 'STORED')"),
    )
    op.drop_table("knowledge_sources")
    op.drop_table("knowledge_upload_policies")
    op.drop_table("user_capabilities")
