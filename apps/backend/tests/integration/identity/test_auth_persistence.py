"""PostgreSQL persistence for digest-only sessions and registration attempts."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from probeinterview.identity.access.application.tokens import (
    SESSION_TTL,
    new_session_token,
    token_digest,
)
from probeinterview.identity.access.infrastructure.auth_stores import (
    SqlAlchemyAuthSessionStore,
    SqlAlchemyRegistrationAttemptStore,
)
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)

BACKEND_ROOT = Path(__file__).resolve().parents[3]

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


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
def identity_engine() -> Engine:
    """Upgrade the production revisions once and remove them after the module."""

    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


def insert_user(engine: Engine) -> UUID:
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
            {"id": user_id, "nickname": "Session User"},
        )
    return user_id


def test_sessions_persist_digests_only_and_stay_independent(
    identity_engine: Engine,
) -> None:
    """Two devices create two rows; neither row contains the plaintext token."""

    user_id = insert_user(identity_engine)
    store = SqlAlchemyAuthSessionStore(create_session_factory(identity_engine))

    first_token = new_session_token()
    second_token = new_session_token()
    store.create(
        user_id=user_id,
        token_digest=token_digest(first_token),
        expires_at=NOW + SESSION_TTL,
    )
    store.create(
        user_id=user_id,
        token_digest=token_digest(second_token),
        expires_at=NOW + SESSION_TTL,
    )

    with identity_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                select user_id, token_digest, expires_at, revoked_at
                from auth_sessions
                order by created_at, id
                """
            )
        ).all()
    assert len(rows) == 2
    assert {row[1] for row in rows} == {
        token_digest(first_token),
        token_digest(second_token),
    }
    assert all(row[2] == NOW + SESSION_TTL for row in rows)
    assert all(row[3] is None for row in rows)
    assert all(first_token != row[1] for row in rows)


def test_session_resolution_enforces_expiry_and_revocation(
    identity_engine: Engine,
) -> None:
    """Only live sessions resolve; expired and revoked digests do not."""

    user_id = insert_user(identity_engine)
    store = SqlAlchemyAuthSessionStore(create_session_factory(identity_engine))

    active_token = new_session_token()
    expired_token = new_session_token()
    revoked_token = new_session_token()
    store.create(
        user_id=user_id,
        token_digest=token_digest(active_token),
        expires_at=NOW + SESSION_TTL,
    )
    store.create(
        user_id=user_id,
        token_digest=token_digest(expired_token),
        expires_at=NOW - timedelta(seconds=1),
    )
    store.create(
        user_id=user_id,
        token_digest=token_digest(revoked_token),
        expires_at=NOW + SESSION_TTL,
    )
    with identity_engine.begin() as connection:
        connection.execute(
            text(
                """
                update auth_sessions
                set revoked_at = :now
                where token_digest = :digest
                """
            ),
            {"now": NOW, "digest": token_digest(revoked_token)},
        )

    assert store.resolve_active(token_digest(active_token), NOW) == user_id
    assert store.resolve_active(token_digest(expired_token), NOW) is None
    assert store.resolve_active(token_digest(revoked_token), NOW) is None
    assert store.resolve_active(token_digest(new_session_token()), NOW) is None


def test_registration_attempts_persist_digest_and_identity_only(
    identity_engine: Engine,
) -> None:
    """Attempts store the digest, provider identity, and expiry — nothing else."""

    store = SqlAlchemyRegistrationAttemptStore(create_session_factory(identity_engine))
    registration_token = new_session_token()
    expires_at = NOW + timedelta(minutes=10)

    store.create(
        app_id="wx-persist-app",
        openid="oPersistOpenId",
        unionid="uPersistUnion",
        token_digest=token_digest(registration_token),
        expires_at=expires_at,
    )

    with identity_engine.connect() as connection:
        row = connection.execute(
            text(
                """
                select token_digest, app_id, openid, unionid, resolved_user_id,
                       consumed_at
                from wechat_registration_attempts
                """
            )
        ).one()
    assert row[0] == token_digest(registration_token)
    assert row[1] == "wx-persist-app"
    assert row[2] == "oPersistOpenId"
    assert row[3] == "uPersistUnion"
    assert row[4] is None
    assert row[5] is None
    assert registration_token not in str(row)
