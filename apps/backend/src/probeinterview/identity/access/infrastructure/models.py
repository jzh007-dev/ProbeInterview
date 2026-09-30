"""Identity-owned SQLAlchemy mappings."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from probeinterview.platform.foundation.infrastructure.persistence import Base


class UserModel(Base):
    """Persisted account display data."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "avatar_object_key IS NULL OR length(btrim(avatar_object_key)) > 0",
            name="ck_users_avatar_object_key_non_blank",
        ),
        UniqueConstraint("avatar_object_key", name="uq_users_avatar_object_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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


class WeChatIdentityModel(Base):
    """External WeChat identity fields reserved for later authentication."""

    __tablename__ = "wechat_identities"
    __table_args__ = (
        UniqueConstraint(
            "app_id",
            "openid",
            name="uq_wechat_identities_app_id_openid",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    openid: Mapped[str] = mapped_column(String(128), nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True)
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


class UserCapabilityModel(Base):
    """Persisted capability assigned to a normal user identity."""

    __tablename__ = "user_capabilities"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    capability: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class WeChatRegistrationAttemptModel(Base):
    """One-time digest-only credential for an unbound WeChat identity."""

    __tablename__ = "wechat_registration_attempts"
    __table_args__ = (
        CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_wechat_registration_attempts_token_digest_hex",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_wechat_registration_attempts_expiry_after_creation",
        ),
        UniqueConstraint(
            "token_digest",
            name="uq_wechat_registration_attempts_token_digest",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    openid: Mapped[str] = mapped_column(String(128), nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolved_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuthSessionModel(Base):
    """Digest-only bearer session truth; plaintext tokens are never stored."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_auth_sessions_token_digest_hex",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_auth_sessions_expiry_after_creation",
        ),
        UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
