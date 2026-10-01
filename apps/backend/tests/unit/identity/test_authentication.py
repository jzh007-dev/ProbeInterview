"""Bearer session authentication invariants."""

from datetime import UTC, datetime
from uuid import UUID

from probeinterview.identity.access.api.dependencies import extract_bearer_token
from probeinterview.identity.access.application.authentication import (
    BearerSessionAuthenticator,
)
from probeinterview.identity.access.application.tokens import token_digest
from probeinterview.identity.access.domain.context import ActorContext

USER_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def test_missing_credential_resolves_nothing_without_persistence_lookup() -> None:
    sessions = StubSessionResolver(USER_ID)
    authenticator = BearerSessionAuthenticator(
        sessions=sessions,
        capabilities=StubCapabilityReader(frozenset()),
        clock=lambda: NOW,
    )

    assert authenticator.authenticate(None) is None
    assert sessions.digests == []
    assert sessions.nows == []


def test_expired_revoked_and_unknown_tokens_resolve_nothing() -> None:
    sessions = StubSessionResolver(None)
    authenticator = BearerSessionAuthenticator(
        sessions=sessions,
        capabilities=StubCapabilityReader(frozenset()),
        clock=lambda: NOW,
    )
    unknown = "a" * 43

    assert authenticator.authenticate(unknown) is None
    assert sessions.digests == [token_digest(unknown)]
    assert sessions.nows == [NOW]


def test_valid_token_resolves_actor_with_capabilities_read_per_request() -> None:
    sessions = StubSessionResolver(USER_ID)
    capabilities = StubCapabilityReader(frozenset({"knowledge.submit_public"}))
    authenticator = BearerSessionAuthenticator(
        sessions=sessions,
        capabilities=capabilities,
        clock=lambda: NOW,
    )
    token = "b" * 43

    first = authenticator.authenticate(token)
    capabilities.capabilities = frozenset()
    second = authenticator.authenticate(token)

    assert first == ActorContext(
        actor_id=USER_ID,
        capabilities=frozenset({"knowledge.submit_public"}),
    )
    assert second == ActorContext(actor_id=USER_ID, capabilities=frozenset())
    assert capabilities.actor_ids == [USER_ID, USER_ID]
    assert sessions.digests == [token_digest(token), token_digest(token)]
    assert sessions.nows == [NOW, NOW]


def test_extract_bearer_token_accepts_only_well_formed_bearer_headers() -> None:
    assert extract_bearer_token("Bearer abc123") == "abc123"
    assert extract_bearer_token("bearer abc123") == "abc123"
    assert extract_bearer_token("Bearer  padded  ") == "padded"


def test_extract_bearer_token_rejects_malformed_headers_without_lookup() -> None:
    malformed = [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Bearer    ",
        "Basic Zm9vOmJhcg==",
        "Bearer token with spaces",
        "Bearer  \x00\x01 ",
        "Bearer 二十字符令牌",
        "Bearer " + "x" * 513,
    ]

    for header in malformed:
        assert extract_bearer_token(header) is None, header


class StubSessionResolver:
    def __init__(self, user_id: UUID | None) -> None:
        self.user_id = user_id
        self.digests: list[str] = []
        self.nows: list[datetime] = []

    def resolve_active(self, token_digest: str, now: datetime) -> UUID | None:
        self.nows.append(now)
        self.digests.append(token_digest)
        return self.user_id


class StubCapabilityReader:
    def __init__(self, capabilities: frozenset[str]) -> None:
        self.capabilities = capabilities
        self.actor_ids: list[UUID] = []

    def get_for_actor(self, actor_id: UUID) -> frozenset[str]:
        self.actor_ids.append(actor_id)
        return self.capabilities
