"""Add avatar object keys, registration attempts, and auth sessions.

Revision ID: 20261001_0003
Revises: 20260930_0002
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261001_0003"
down_revision: str | None = "20260930_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store provider-neutral avatar keys and credential/session digests only."""

    op.add_column(
        "users",
        sa.Column("avatar_object_key", sa.String(length=1024), nullable=True),
    )
    op.drop_column("users", "avatar_url")
    op.create_check_constraint(
        "ck_users_avatar_object_key_non_blank",
        "users",
        "avatar_object_key IS NULL OR length(btrim(avatar_object_key)) > 0",
    )
    op.create_unique_constraint(
        "uq_users_avatar_object_key",
        "users",
        ["avatar_object_key"],
    )

    op.create_table(
        "wechat_registration_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
        sa.Column("resolved_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_wechat_registration_attempts_token_digest_hex",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_wechat_registration_attempts_expiry_after_creation",
        ),
        sa.ForeignKeyConstraint(["resolved_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_digest",
            name="uq_wechat_registration_attempts_token_digest",
        ),
    )
    op.create_index(
        "ix_wechat_registration_attempts_identity",
        "wechat_registration_attempts",
        ["app_id", "openid"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_auth_sessions_token_digest_hex",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_auth_sessions_expiry_after_creation",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
    )


def downgrade() -> None:
    """Remove credential/session tables and restore the avatar URL column."""

    op.drop_table("auth_sessions")
    op.drop_index(
        "ix_wechat_registration_attempts_identity",
        table_name="wechat_registration_attempts",
    )
    op.drop_table("wechat_registration_attempts")
    op.drop_constraint("uq_users_avatar_object_key", "users", type_="unique")
    op.drop_constraint("ck_users_avatar_object_key_non_blank", "users", type_="check")
    op.add_column(
        "users",
        sa.Column(
            "avatar_url",
            sa.String(length=2048),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.alter_column("users", "avatar_url", server_default=None)
    op.drop_column("users", "avatar_object_key")
