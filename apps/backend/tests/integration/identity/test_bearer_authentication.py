"""PostgreSQL-backed acceptance coverage for bearer session authentication."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, text

from probeinterview.entrypoints.api import create_app
from probeinterview.identity.access.application.authentication import (
    BearerSessionAuthenticator,
)
from probeinterview.identity.access.application.tokens import (
    SESSION_TTL,
    new_session_token,
    token_digest,
)
from probeinterview.identity.access.infrastructure.auth_stores import (
    SqlAlchemyAuthSessionStore,
)
from probeinterview.identity.access.infrastructure.queries import (
    SqlAlchemyCapabilityReader,
)
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.asyncio

BACKEND_ROOT = Path(__file__).resolve().parents[3]

# The HTTP path authenticates with the real process clock, so expiry and
# revocation timestamps anchor to import time instead of a fixed instant.
NOW = datetime.now(UTC)
CAPABILITY = "knowledge.submit_public"


def isolated_database_url() -> str:
    """Return only a database created by the destructive integration runner."""

    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/verify --full")
    if os.getenv("PROBEINTERVIEW_DESTRUCTIVE_DATABASE_TEST") != "1":
        raise RuntimeError("destructive database test sentinel is required")
    if "/probeinterview_identity_test_" not in database_url:
        raise RuntimeError("refusing to migrate a non-isolated database")
    return database_url


@pytest.fixture(scope="module")
def identity_database() -> Iterator[tuple[str, Engine]]:
    """Upgrade the production revisions once and remove them after the module."""

    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        yield database_url, engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


async def test_missing_malformed_and_non_bearer_headers_are_stable_401s(
    identity_database: tuple[str, Engine],
) -> None:
    """Every unusable Authorization header maps to one stable problem."""

    async with authenticated_client(identity_database[0]) as client:
        for header in (
            None,
            "",
            "Basic Zm9vOmJhcg==",
            "Bearer",
            "Bearer ",
            "Bearer    ",
            "Bearer token with spaces",
            # A multibyte credential can only reach the server as raw bytes.
            b"Bearer \xe4\xbb\xa4\xe7\x89\x8c",
        ):
            headers: dict[str, str | bytes] = {} if header is None else {"Authorization": header}
            response = await client.get("/api/v1/me/overview", headers=headers)

            assert response.status_code == 401, header
            assert response.headers["content-type"] == "application/problem+json"
            problem = response.json()
            assert problem["code"] == "authentication_required"
            assert problem["status"] == 401
            assert problem["detail"] == "A valid bearer session is required."


async def test_unknown_expired_and_revoked_tokens_are_stable_401s(
    identity_database: tuple[str, Engine],
) -> None:
    """Digest resolution rejects everything that is not a live session."""

    engine = identity_database[1]
    user_id = insert_user(engine, "Expiry User")
    store = SqlAlchemyAuthSessionStore(create_session_factory(engine))
    expired_token = new_session_token()
    revoked_token = new_session_token()
    # The session table requires expiry after creation, so the expired row is
    # backdated explicitly.
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into auth_sessions (id, user_id, token_digest, created_at, expires_at)
                values (:id, :user_id, :digest, :created_at, :expires_at)
                """
            ),
            {
                "id": uuid4(),
                "user_id": user_id,
                "digest": token_digest(expired_token),
                "created_at": NOW - timedelta(hours=1),
                "expires_at": NOW - timedelta(seconds=1),
            },
        )
    store.create(
        user_id=user_id,
        token_digest=token_digest(revoked_token),
        expires_at=NOW + SESSION_TTL,
    )
    with engine.begin() as connection:
        connection.execute(
            text("update auth_sessions set revoked_at = :now where token_digest = :digest"),
            {"now": NOW, "digest": token_digest(revoked_token)},
        )

    async with authenticated_client(identity_database[0]) as client:
        for token in (new_session_token(), expired_token, revoked_token):
            response = await client.get(
                "/api/v1/me/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 401, token
            assert response.json()["code"] == "authentication_required"


async def test_valid_session_resolves_owner_scoped_overview(
    identity_database: tuple[str, Engine],
) -> None:
    """A live digest resolves the owning user's overview and nothing else."""

    engine = identity_database[1]
    user_id = insert_user_with_default_profile(engine, "Overview Owner")
    token = issue_session(engine, user_id)

    async with authenticated_client(identity_database[0]) as client:
        response = await client.get(
            "/api/v1/me/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["nickname"] == "Overview Owner"
    assert "token_digest" not in body


async def test_two_sessions_resolve_only_their_own_overview(
    identity_database: tuple[str, Engine],
) -> None:
    """Two users' tokens stay isolated; neither sees the other's identity."""

    engine = identity_database[1]
    first_id = insert_user_with_default_profile(engine, "First Owner")
    second_id = insert_user_with_default_profile(engine, "Second Owner")
    first_token = issue_session(engine, first_id)
    second_token = issue_session(engine, second_id)

    async with authenticated_client(identity_database[0]) as client:
        first = await client.get(
            "/api/v1/me/overview",
            headers={"Authorization": f"Bearer {first_token}"},
        )
        second = await client.get(
            "/api/v1/me/overview",
            headers={"Authorization": f"Bearer {second_token}"},
        )

    assert first.json()["nickname"] == "First Owner"
    assert second.json()["nickname"] == "Second Owner"
    assert "First Owner" not in second.text


async def test_capability_changes_apply_on_the_next_authentication(
    identity_database: tuple[str, Engine],
) -> None:
    """Capabilities are re-read per authentication, never cached on the actor."""

    engine = identity_database[1]
    user_id = insert_user(engine, "Capability User")
    token = issue_session(engine, user_id)
    session_factory = create_session_factory(engine)
    authenticator = BearerSessionAuthenticator(
        sessions=SqlAlchemyAuthSessionStore(session_factory),
        capabilities=SqlAlchemyCapabilityReader(session_factory),
        clock=lambda: NOW,
    )

    before = authenticator.authenticate(token)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into user_capabilities (user_id, capability)
                values (:user_id, :capability)
                """
            ),
            {"user_id": user_id, "capability": CAPABILITY},
        )
    after = authenticator.authenticate(token)

    assert before is not None
    assert after is not None
    assert before.capabilities == frozenset()
    assert after.capabilities == frozenset({CAPABILITY})


def insert_user(engine: Engine, nickname: str) -> UUID:
    """Insert one user and return its generated id."""

    user_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, null)
                """
            ),
            {"id": user_id, "nickname": nickname},
        )
    return user_id


def insert_user_with_default_profile(engine: Engine, nickname: str) -> UUID:
    """Insert one user whose overview satisfies the current profile contract."""

    user_id = insert_user(engine, nickname)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:id, :user_id, 'Platform Engineer', 24, true)
                """
            ),
            {"id": uuid4(), "user_id": user_id},
        )
    return user_id


def issue_session(engine: Engine, user_id: UUID) -> str:
    """Create one live 30-day session and return its plaintext token."""

    token = new_session_token()
    store = SqlAlchemyAuthSessionStore(create_session_factory(engine))
    store.create(
        user_id=user_id,
        token_digest=token_digest(token),
        expires_at=NOW + SESSION_TTL,
    )
    return token


def authenticated_client(database_url: str) -> AsyncClient:
    """Build one API client over the production wechat+fake configuration."""

    settings = Settings(
        environment="test",
        database_url=database_url,
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="bearer-integration",
        foundation_probe_enabled=False,
        _env_file=None,
    )
    app = create_app(settings=settings, readiness_checks={})
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
