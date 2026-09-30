"""PostgreSQL serialization and convergence for first registrations."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.identity.access.application.registration import (
    RegistrationStoreCommand,
    RegistrationTokenInvalid,
)
from probeinterview.identity.access.infrastructure.models import (
    AuthSessionModel,
    UserModel,
    WeChatIdentityModel,
    WeChatRegistrationAttemptModel,
)


class SqlAlchemyRegistrationStore:
    """Register one identity under attempt-row and identity-scoped locks."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register(
        self,
        command: RegistrationStoreCommand,
        upload_avatar: Callable[[UUID, UUID], str | None],
    ) -> UUID:
        """Return the winning user id after commit.

        The attempt row lock serializes same-credential races and the
        transaction-scoped advisory lock serializes one (app_id, openid);
        the existing unique constraint remains the final integrity guard.
        """

        with self._session_factory() as session, session.begin():
            attempt = session.scalar(
                select(WeChatRegistrationAttemptModel)
                .where(WeChatRegistrationAttemptModel.token_digest == command.registration_digest)
                .with_for_update()
            )
            if attempt is None:
                raise RegistrationTokenInvalid
            self._lock_identity(session, attempt.app_id, attempt.openid)

            bound_user_id = session.scalar(
                select(WeChatIdentityModel.user_id).where(
                    WeChatIdentityModel.app_id == attempt.app_id,
                    WeChatIdentityModel.openid == attempt.openid,
                )
            )
            if bound_user_id is not None:
                if attempt.consumed_at is not None and attempt.resolved_user_id != bound_user_id:
                    raise RegistrationTokenInvalid
                self._consume_attempt(session, attempt, bound_user_id, command.now)
                self._create_session(session, bound_user_id, command)
                return bound_user_id

            if attempt.consumed_at is not None:
                raise RegistrationTokenInvalid
            if attempt.expires_at <= command.now:
                raise RegistrationTokenInvalid

            user_id = uuid4()
            avatar_id = uuid4()
            object_key = upload_avatar(user_id, avatar_id)
            session.add(
                UserModel(id=user_id, nickname=command.nickname, avatar_object_key=object_key)
            )
            session.add(
                WeChatIdentityModel(
                    id=uuid4(),
                    user_id=user_id,
                    app_id=attempt.app_id,
                    openid=attempt.openid,
                    unionid=attempt.unionid,
                )
            )
            # There are no relationship() declarations across these tables,
            # so flush explicitly to insert users and identities first.
            session.flush()
            self._create_session(session, user_id, command)
            self._consume_attempt(session, attempt, user_id, command.now)
            return user_id

    @staticmethod
    def _lock_identity(session: Session, app_id: str, openid: str) -> None:
        """Acquire the transaction-scoped advisory lock for one identity."""

        session.execute(
            text("select pg_advisory_xact_lock(hashtext(:app_id), hashtext(:openid))"),
            {"app_id": app_id, "openid": openid},
        )

    @staticmethod
    def _create_session(
        session: Session,
        user_id: UUID,
        command: RegistrationStoreCommand,
    ) -> None:
        session.add(
            AuthSessionModel(
                user_id=user_id,
                token_digest=command.session_digest,
                expires_at=command.session_expires_at,
            )
        )

    @staticmethod
    def _consume_attempt(
        session: Session,
        attempt: WeChatRegistrationAttemptModel,
        user_id: UUID,
        now: datetime,
    ) -> None:
        attempt.consumed_at = now
        attempt.resolved_user_id = user_id
