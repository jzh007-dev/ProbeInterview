"""WeChat code exchange orchestration for login and first registration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from probeinterview.identity.access.application.tokens import (
    REGISTRATION_TOKEN_TTL,
    SESSION_TTL,
    new_registration_token,
    new_session_token,
    token_digest,
)
from probeinterview.identity.access.application.wechat import WeChatIdentityExchange


class MissingBoundUser(Exception):
    """A persisted binding points at a user that no longer exists."""


@dataclass(frozen=True, slots=True)
class ExchangeTargetProfile:
    """Display-safe summary of the actor's explicit default target profile."""

    target_role: str
    relevant_experience_months: int


@dataclass(frozen=True, slots=True)
class ExchangeSnapshot:
    """Typed current-user display snapshot rebuilt from server truth."""

    user_id: UUID
    nickname: str
    avatar_object_key: str | None
    default_target_profile: ExchangeTargetProfile | None
    capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class AuthenticatedExchange:
    """A new bearer session plus the fresh current-user snapshot."""

    access_token: str
    token_type: str
    expires_at: datetime
    current_user: ExchangeSnapshot


@dataclass(frozen=True, slots=True)
class RegistrationRequired:
    """A short-lived one-time credential for the first-registration flow."""

    registration_token: str
    expires_at: datetime


class WeChatBindingReader(Protocol):
    """Resolve whether a provider identity already belongs to a user."""

    def find_user_id(self, app_id: str, openid: str) -> UUID | None:
        """Return the bound user id, or None when the identity is unbound."""


class ExchangeSnapshotReader(Protocol):
    """Rebuild the display snapshot from current persisted state."""

    def get_snapshot(self, user_id: UUID) -> ExchangeSnapshot | None:
        """Return the snapshot for user_id, or None when it is missing."""


class AuthSessionStore(Protocol):
    """Persist digest-only bearer sessions."""

    def create(
        self,
        *,
        user_id: UUID,
        token_digest: str,
        expires_at: datetime,
    ) -> None:
        """Store one new session keyed by its token digest."""


class RegistrationAttemptStore(Protocol):
    """Persist digest-only one-time registration credentials."""

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


class WeChatExchangeService:
    """Resolve one login code into a session or a registration credential."""

    def __init__(
        self,
        *,
        wechat: WeChatIdentityExchange,
        bindings: WeChatBindingReader,
        snapshots: ExchangeSnapshotReader,
        sessions: AuthSessionStore,
        attempts: RegistrationAttemptStore,
        app_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._wechat = wechat
        self._bindings = bindings
        self._snapshots = snapshots
        self._sessions = sessions
        self._attempts = attempts
        self._app_id = app_id
        self._clock = clock or (lambda: datetime.now(UTC))

    def exchange(self, code: str) -> AuthenticatedExchange | RegistrationRequired:
        """Return the discriminated result for one WeChat login code."""

        identity = self._wechat.exchange(code)
        now = self._clock().astimezone(UTC)
        user_id = self._bindings.find_user_id(self._app_id, identity.openid)
        if user_id is None:
            registration_token = new_registration_token()
            self._attempts.create(
                app_id=self._app_id,
                openid=identity.openid,
                unionid=identity.unionid,
                token_digest=token_digest(registration_token),
                expires_at=now + REGISTRATION_TOKEN_TTL,
            )
            return RegistrationRequired(
                registration_token=registration_token,
                expires_at=now + REGISTRATION_TOKEN_TTL,
            )

        snapshot = self._snapshots.get_snapshot(user_id)
        if snapshot is None:
            raise MissingBoundUser
        access_token = new_session_token()
        expires_at = now + SESSION_TTL
        self._sessions.create(
            user_id=user_id,
            token_digest=token_digest(access_token),
            expires_at=expires_at,
        )
        return AuthenticatedExchange(
            access_token=access_token,
            token_type="Bearer",
            expires_at=expires_at,
            current_user=snapshot,
        )
