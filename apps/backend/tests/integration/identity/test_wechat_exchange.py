"""API-level acceptance for WeChat exchange against real persistence."""

import os
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, text

from probeinterview.entrypoints.api import create_app
from probeinterview.identity.access.application.tokens import (
    SESSION_TTL,
    token_digest,
)
from probeinterview.platform.foundation.infrastructure.persistence import create_engine
from probeinterview.platform.foundation.infrastructure.settings import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ID = "wx-exchange-app"
KNOWN_OPENID = "oExchangeKnownOpenId"


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


def make_settings(database_url: str) -> Settings:
    """Return deterministic wechat + fake settings for the isolated database."""

    return Settings(
        environment="test",
        database_url=database_url,
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id=APP_ID,
        demo_profile_seed_enabled=False,
        foundation_probe_enabled=False,
        _env_file=None,
    )


@pytest.fixture()
def exchange_database_url() -> str:
    """Upgrade the production revisions and return the isolated database URL."""

    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    return database_url


@pytest.fixture()
def exchange_database(exchange_database_url: str) -> Iterator[Engine]:
    """Yield one engine and remove the revisions after the module."""

    engine = create_engine(exchange_database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        config = Config(BACKEND_ROOT / "alembic.ini")
        config.attributes["database_url"] = exchange_database_url
        command.downgrade(config, "base")


def insert_bound_user(engine: Engine, openid: str) -> UUID:
    """Insert one user with one bound WeChat identity and return the user id."""

    user_id = uuid4()
    identity_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, null)
                """
            ),
            {"id": user_id, "nickname": "交换用户"},
        )
        connection.execute(
            text(
                """
                insert into wechat_identities (id, user_id, app_id, openid, unionid)
                values (:id, :user_id, :app_id, :openid, null)
                """
            ),
            {
                "id": identity_id,
                "user_id": user_id,
                "app_id": APP_ID,
                "openid": openid,
            },
        )
    return user_id


async def post_exchange(database_url: str, code: str) -> tuple[Response, AsyncClient]:
    """Create one app against the isolated database and post one exchange."""

    app = create_app(settings=make_settings(database_url), readiness_checks={})
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    await client.__aenter__()
    response = await client.post("/api/v1/auth/wechat/exchanges", json={"code": code})
    return response, client


@pytest.mark.asyncio
async def test_registered_identity_receives_session_and_snapshot(
    exchange_database_url: str,
    exchange_database: Engine,
) -> None:
    """A bound identity logs in with a new session whose digest is persisted."""

    expected_user_id = insert_bound_user(exchange_database, KNOWN_OPENID)

    response, client = await post_exchange(exchange_database_url, KNOWN_OPENID)
    try:
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "authenticated"
        assert payload["token_type"] == "Bearer"
        access_token = payload["access_token"]
        assert payload["current_user"] == {
            "id": str(expected_user_id),
            "nickname": "交换用户",
            "avatar_url": None,
            "avatar_url_expires_at": None,
            "default_target_profile": None,
        }

        digest = token_digest(access_token)
        with exchange_database.connect() as connection:
            row = connection.execute(
                text(
                    """
                    select user_id, token_digest from auth_sessions
                    where token_digest = :digest
                    """
                ),
                {"digest": digest},
            ).one()
        assert row[0] == expected_user_id
        assert access_token not in str(row)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_session_expiry_is_exactly_thirty_days(
    exchange_database_url: str,
    exchange_database: Engine,
) -> None:
    """The authenticated expiry matches the persisted 30-day issuance bound."""

    insert_bound_user(exchange_database, KNOWN_OPENID + "-expiry")

    response, client = await post_exchange(exchange_database_url, KNOWN_OPENID + "-expiry")
    try:
        assert response.status_code == 200
        payload = response.json()
        digest = token_digest(payload["access_token"])
        with exchange_database.connect() as connection:
            created_at, expires_at = connection.execute(
                text(
                    """
                    select created_at, expires_at from auth_sessions
                    where token_digest = :digest
                    """
                ),
                {"digest": digest},
            ).one()
        delta = expires_at - created_at
        assert abs(delta - SESSION_TTL) < timedelta(seconds=5)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unbound_identity_receives_only_a_registration_credential(
    exchange_database_url: str,
    exchange_database: Engine,
) -> None:
    """An unbound identity creates one attempt row and no user or session."""

    unknown_openid = "oExchangeUnknownOpenId"

    response, client = await post_exchange(exchange_database_url, unknown_openid)
    try:
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "registration_required"
        registration_token = payload["registration_token"]

        with exchange_database.connect() as connection:
            attempts = connection.execute(
                text(
                    """
                    select token_digest, openid, resolved_user_id, consumed_at
                    from wechat_registration_attempts
                    where openid = :openid
                    """
                ),
                {"openid": unknown_openid},
            ).all()
            sessions = connection.execute(text("select count(*) from auth_sessions")).scalar()
            users = connection.execute(text("select count(*) from users")).scalar()
        assert len(attempts) == 1
        assert attempts[0][1] == unknown_openid
        assert attempts[0][2] is None
        assert attempts[0][3] is None
        assert attempts[0][0] == token_digest(registration_token)
        assert registration_token not in str(attempts)
        assert sessions == 0
        assert users == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_response_and_logs_never_contain_provider_or_token_secrets(
    exchange_database_url: str,
    exchange_database: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected codes and outages leak neither codes nor openid nor secrets."""

    secret_openid = "oExchangeSensitiveOpenId"

    rejected, client = await post_exchange(exchange_database_url, "invalid-code")
    try:
        assert rejected.status_code == 400
        problem = rejected.json()
        assert problem["code"] == "wechat_code_exchange_failed"
        assert secret_openid not in rejected.text
        assert "session_key" not in rejected.text
    finally:
        await client.aclose()

    outage, client = await post_exchange(exchange_database_url, "timeout-code")
    try:
        assert outage.status_code == 503
        assert outage.json()["code"] == "wechat_service_unavailable"
    finally:
        await client.aclose()

    assert "invalid-code" not in caplog.text
    assert "timeout-code" not in caplog.text
    assert secret_openid not in caplog.text
    assert "session_key" not in caplog.text
    assert APP_ID not in caplog.text
