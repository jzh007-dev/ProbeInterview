"""Exchange service orchestration covers session and registration boundaries."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from probeinterview.identity.access.application.exchange import (
    ExchangeSnapshot,
    ExchangeTargetProfile,
    MissingBoundUser,
    RegistrationRequired,
    WeChatExchangeService,
)
from probeinterview.identity.access.application.tokens import (
    REGISTRATION_TOKEN_TTL,
    SESSION_TTL,
    new_session_token,
    token_digest,
)
from probeinterview.identity.access.application.wechat import (
    WeChatCodeExchangeFailed,
    WeChatIdentity,
    WeChatServiceUnavailable,
)

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
APP_ID = "wx-unit-app"
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)

SNAPSHOT = ExchangeSnapshot(
    user_id=ACTOR_ID,
    nickname="Bao",
    avatar_object_key=None,
    default_target_profile=ExchangeTargetProfile(
        target_role="AI 全栈开发",
        relevant_experience_months=84,
    ),
    capabilities=frozenset({"knowledge.submit_public"}),
)


class FakeWeChat:
    def __init__(self, identity: WeChatIdentity | None = None, error: Exception | None = None):
        self.identity = identity
        self.error = error
        self.requested_codes: list[str] = []

    def exchange(self, code: str) -> WeChatIdentity:
        self.requested_codes.append(code)
        if self.error is not None:
            raise self.error
        assert self.identity is not None
        return self.identity


class FakeBindings:
    def __init__(self, bound: dict[str, UUID] | None = None):
        self.bound = bound or {}

    def find_user_id(self, app_id: str, openid: str) -> UUID | None:
        return self.bound.get((app_id, openid))


class FakeSnapshots:
    def __init__(self, snapshots: dict[UUID, ExchangeSnapshot] | None = None):
        self.snapshots = snapshots or {}
        self.requested_user_ids: list[UUID] = []

    def get_snapshot(self, user_id: UUID) -> ExchangeSnapshot | None:
        self.requested_user_ids.append(user_id)
        return self.snapshots.get(user_id)


class FakeSessions:
    def __init__(self):
        self.created: list[dict[str, object]] = []

    def create(self, *, user_id: UUID, token_digest: str, expires_at: datetime) -> None:
        self.created.append(
            {"user_id": user_id, "token_digest": token_digest, "expires_at": expires_at}
        )


class FakeAttempts:
    def __init__(self):
        self.created: list[dict[str, object]] = []

    def create(
        self,
        *,
        app_id: str,
        openid: str,
        unionid: str | None,
        token_digest: str,
        expires_at: datetime,
    ) -> None:
        self.created.append(
            {
                "app_id": app_id,
                "openid": openid,
                "unionid": unionid,
                "token_digest": token_digest,
                "expires_at": expires_at,
            }
        )


def make_service(
    wechat: FakeWeChat,
    bindings: FakeBindings,
    snapshots: FakeSnapshots,
    sessions: FakeSessions,
    attempts: FakeAttempts,
) -> WeChatExchangeService:
    return WeChatExchangeService(
        wechat=wechat,
        bindings=bindings,
        snapshots=snapshots,
        sessions=sessions,
        attempts=attempts,
        app_id=APP_ID,
        clock=lambda: NOW,
    )


def test_registered_identity_returns_fresh_session_and_snapshot() -> None:
    wechat = FakeWeChat(identity=WeChatIdentity(openid="oKnown", unionid=None))
    bindings = FakeBindings({(APP_ID, "oKnown"): ACTOR_ID})
    snapshots = FakeSnapshots({ACTOR_ID: SNAPSHOT})
    sessions = FakeSessions()
    attempts = FakeAttempts()
    service = make_service(wechat, bindings, snapshots, sessions, attempts)

    result = service.exchange("login-code")

    assert isinstance(result, RegistrationRequired) is False
    assert result.token_type == "Bearer"
    assert result.expires_at == NOW + SESSION_TTL
    assert result.current_user is SNAPSHOT
    assert result.access_token and token_digest(result.access_token)
    assert sessions.created == [
        {
            "user_id": ACTOR_ID,
            "token_digest": token_digest(result.access_token),
            "expires_at": NOW + SESSION_TTL,
        }
    ]
    assert attempts.created == []
    assert snapshots.requested_user_ids == [ACTOR_ID]


def test_unbound_identity_creates_only_a_registration_attempt() -> None:
    wechat = FakeWeChat(identity=WeChatIdentity(openid="oUnknown", unionid="uUnion"))
    sessions = FakeSessions()
    attempts = FakeAttempts()
    service = make_service(wechat, FakeBindings(), FakeSnapshots(), sessions, attempts)

    result = service.exchange("login-code")

    assert isinstance(result, RegistrationRequired)
    assert result.expires_at == NOW + REGISTRATION_TOKEN_TTL
    assert attempts.created == [
        {
            "app_id": APP_ID,
            "openid": "oUnknown",
            "unionid": "uUnion",
            "token_digest": token_digest(result.registration_token),
            "expires_at": result.expires_at,
        }
    ]
    assert sessions.created == []


def test_wechat_rejection_propagates_without_any_persistence() -> None:
    for error in (WeChatCodeExchangeFailed(), WeChatServiceUnavailable()):
        wechat = FakeWeChat(error=error)
        sessions = FakeSessions()
        attempts = FakeAttempts()
        service = make_service(wechat, FakeBindings(), FakeSnapshots(), sessions, attempts)

        with pytest.raises(type(error)):
            service.exchange("login-code")

        assert sessions.created == []
        assert attempts.created == []


def test_binding_without_snapshot_is_a_safe_internal_error() -> None:
    wechat = FakeWeChat(identity=WeChatIdentity(openid="oKnown", unionid=None))
    bindings = FakeBindings({(APP_ID, "oKnown"): ACTOR_ID})
    sessions = FakeSessions()
    attempts = FakeAttempts()
    service = make_service(wechat, bindings, FakeSnapshots(), sessions, attempts)

    with pytest.raises(MissingBoundUser):
        service.exchange("login-code")

    assert sessions.created == []
    assert attempts.created == []


def test_service_never_persists_plaintext_tokens() -> None:
    wechat = FakeWeChat(identity=WeChatIdentity(openid="oKnown", unionid=None))
    bindings = FakeBindings({(APP_ID, "oKnown"): ACTOR_ID})
    snapshots = FakeSnapshots({ACTOR_ID: SNAPSHOT})
    sessions = FakeSessions()
    service = make_service(wechat, bindings, snapshots, sessions, FakeAttempts())

    result = service.exchange("login-code")

    assert isinstance(result, RegistrationRequired) is False
    stored_digests = {entry["token_digest"] for entry in sessions.created}
    assert token_digest(result.access_token) in stored_digests
    assert result.access_token not in {str(digest) for digest in stored_digests}
    # A distinct token never matches a stored digest.
    assert token_digest(new_session_token()) not in stored_digests
