"""SQLAlchemy identity display query adapter."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.identity.access.application.queries import IdentityDisplay
from probeinterview.identity.access.infrastructure.models import UserModel


class SqlAlchemyIdentityDisplayReader:
    """Read only the actor-owned user display record."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_for_actor(self, actor_id: UUID) -> IdentityDisplay | None:
        with self._session_factory() as session:
            user = session.scalar(select(UserModel).where(UserModel.id == actor_id))
        if user is None:
            return None
        return IdentityDisplay(
            id=user.id,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
        )
