"""SQLAlchemy persistence for identity exchange, sessions, and attempts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.identity.access.application.exchange import (
    ExchangeSnapshot,
)
from probeinterview.identity.access.infrastructure.models import (
    AuthSessionModel,
    UserCapabilityModel,
    UserModel,
    WeChatIdentityModel,
    WeChatRegistrationAttemptModel,
)


class SqlAlchemyWeChatBindingReader:
    """Resolve the user bound to one configured WeChat identity."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find_user_id(self, app_id: str, openid: str) -> UUID | None:
        """Return the bound user id, or None when the identity is unbound."""

        with self._session_factory() as session:
            return session.scalar(
                select(WeChatIdentityModel.user_id).where(
                    WeChatIdentityModel.app_id == app_id,
                    WeChatIdentityModel.openid == openid,
                )
            )


class SqlAlchemyAuthSessionStore:
    """Persist digest-only bearer sessions and resolve them safely."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        user_id: UUID,
        token_digest: str,
        expires_at: datetime,
    ) -> None:
        """Store one new session keyed by its token digest."""

        with self._session_factory() as session, session.begin():
            session.add(
                AuthSessionModel(
                    user_id=user_id,
                    token_digest=token_digest,
                    expires_at=expires_at,
                )
            )

    def resolve_active(self, token_digest: str, now: datetime) -> UUID | None:
        """Return the user id when the digest maps to a live session."""

        with self._session_factory() as session:
            return session.scalar(
                select(AuthSessionModel.user_id).where(
                    AuthSessionModel.token_digest == token_digest,
                    AuthSessionModel.revoked_at.is_(None),
                    AuthSessionModel.expires_at > now,
                )
            )


class SqlAlchemyRegistrationAttemptStore:
    """Persist digest-only one-time registration credentials."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        app_id: str,
        openid: str,
        unionid: str | None,
        token_digest: str,
        expires_at: datetime,
    ) -> None:
        """Store one new registration attempt keyed by its token digest."""

        with self._session_factory() as session, session.begin():
            session.add(
                WeChatRegistrationAttemptModel(
                    token_digest=token_digest,
                    app_id=app_id,
                    openid=openid,
                    unionid=unionid,
                    expires_at=expires_at,
                )
            )


class SqlAlchemyExchangeSnapshotReader:
    """Rebuild the identity-owned part of the current-user snapshot."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_snapshot(self, user_id: UUID) -> ExchangeSnapshot | None:
        """Return the identity-owned snapshot fields for user_id.

        The default target profile stays None here; the composition root
        enriches the snapshot through the candidate profile contract.
        """

        with self._session_factory() as session:
            user = session.scalar(select(UserModel).where(UserModel.id == user_id))
            if user is None:
                return None
            capabilities = frozenset(
                session.scalars(
                    select(UserCapabilityModel.capability).where(
                        UserCapabilityModel.user_id == user_id
                    )
                ).all()
            )
        return ExchangeSnapshot(
            user_id=user.id,
            nickname=user.nickname,
            avatar_object_key=user.avatar_object_key,
            default_target_profile=None,
            capabilities=capabilities,
        )
