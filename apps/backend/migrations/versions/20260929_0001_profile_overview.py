"""Create persisted identity and candidate profile overview data.

Revision ID: 20260929_0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create identity and candidate-owned profile overview tables."""

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=False),
        sa.Column("avatar_url", sa.String(length=2048), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "wechat_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "app_id",
            "openid",
            name="uq_wechat_identities_app_id_openid",
        ),
    )
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_role", sa.String(length=200), nullable=False),
        sa.Column("relevant_experience_months", sa.Integer(), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            "relevant_experience_months >= 0",
            name="ck_candidate_profiles_experience_non_negative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_candidate_profiles_default_per_user",
        "candidate_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE"),
    )
    op.create_table(
        "user_resume",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_file_name", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_object_key", sa.String(length=1024), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64",
            name="ck_user_resume_content_sha256_length",
        ),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_user_resume_revision_positive",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_user_resume_size_non_negative",
        ),
        sa.CheckConstraint(
            "length(btrim(storage_object_key)) > 0",
            name="ck_user_resume_storage_object_key_non_blank",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_object_key",
            name="uq_user_resume_storage_object_key",
        ),
        sa.UniqueConstraint("user_id", name="uq_user_resume_user_id"),
    )


def downgrade() -> None:
    """Remove only the profile overview tables introduced by this revision."""

    op.drop_table("user_resume")
    op.drop_index(
        "uq_candidate_profiles_default_per_user",
        table_name="candidate_profiles",
        postgresql_where=sa.text("is_default IS TRUE"),
    )
    op.drop_table("candidate_profiles")
    op.drop_table("wechat_identities")
    op.drop_table("users")
