"""Concurrent first registrations converge to one user per identity."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, text

from probeinterview.entrypoints.api import create_app
from probeinterview.platform.foundation.infrastructure.persistence import create_engine
from probeinterview.platform.foundation.infrastructure.settings import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ID = "wx-concurrency-app"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"race-payload"


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
def database_url() -> str:
    """Upgrade the production revisions once per test and remove them after."""

    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    try:
        yield database_url
    finally:
        command.downgrade(config, "base")


@pytest.fixture()
def database(database_url: str) -> Engine:
    return create_engine(database_url)


async def exchange(database_url: str, openid: str) -> str:
    """Return one live registration token for one unbound identity."""

    app = create_app(settings=make_settings(database_url), readiness_checks={})
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    try:
        response = await client.post("/api/v1/auth/wechat/exchanges", json={"code": openid})
    finally:
        await client.aclose()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "registration_required"
    return str(payload["registration_token"])


def post_registration(
    database_url: str,
    registration_token: str,
    nickname: str,
) -> tuple[int, dict[str, object]]:
    """Post one JSON registration from a worker thread."""

    app = create_app(settings=make_settings(database_url), readiness_checks={})

    async def run() -> tuple[int, dict[str, object]]:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        try:
            response = await client.post(
                "/api/v1/auth/wechat/registrations",
                json={"registration_token": registration_token, "nickname": nickname},
            )
        finally:
            await client.aclose()
        return response.status_code, response.json()

    return asyncio.run(run())


def registration_shape(database: Engine) -> tuple[int, int, int, int]:
    """Return user, identity, session, and stored avatar object counts."""

    with database.connect() as connection:
        users = connection.execute(text("select count(*) from users")).scalar()
        identities = connection.execute(text("select count(*) from wechat_identities")).scalar()
        sessions = connection.execute(text("select count(*) from auth_sessions")).scalar()
        avatars = connection.execute(
            text("select count(*) from users where avatar_object_key is not null")
        ).scalar()
    return int(users), int(identities), int(sessions), int(avatars)


def asyncio_run_exchange(database_url: str, openid: str) -> str:
    """Bridge the async exchange helper for the synchronous test body."""

    return asyncio.run(exchange(database_url, openid))


def test_same_token_races_converge_to_one_user(
    database_url: str,
    database: Engine,
) -> None:
    """Two concurrent same-token registrations yield one user with sessions."""

    registration_token = asyncio_run_exchange(database_url, "oRaceSameOpenId")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: post_registration(database_url, registration_token, "竞速用户"),
                range(2),
            )
        )

    assert all(status == 200 for status, _ in results)
    winner_ids = {payload["current_user"]["id"] for _, payload in results}
    assert len(winner_ids) == 1

    users, identities, sessions, avatars = registration_shape(database)
    assert (users, identities, avatars) == (1, 1, 0)
    assert sessions == 2


def test_distinct_token_races_converge_and_store_one_avatar(
    database_url: str,
    database: Engine,
) -> None:
    """Two tokens for one identity race custom avatars; one object survives."""

    openid = "oRaceAvatarOpenId"
    tokens = [asyncio_run_exchange(database_url, openid) for _ in range(2)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: post_avatar_registration(*args),
                [(database_url, token, "竞速头像") for token in tokens],
            )
        )

    assert all(status == 200 for status, _ in results)
    winner_ids = {payload["current_user"]["id"] for _, payload in results}
    assert len(winner_ids) == 1

    users, identities, sessions, avatars = registration_shape(database)
    assert (users, identities) == (1, 1)
    assert avatars == 1
    assert sessions == 2


def post_avatar_registration(
    database_url: str,
    registration_token: str,
    nickname: str,
) -> tuple[int, dict[str, object]]:
    """Post one multipart registration from a worker thread."""

    app = create_app(settings=make_settings(database_url), readiness_checks={})

    async def run() -> tuple[int, dict[str, object]]:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        try:
            response = await client.post(
                "/api/v1/auth/wechat/avatar-registrations",
                data={"registration_token": registration_token, "nickname": nickname},
                files={"file": ("avatar.png", PNG_BYTES, "image/png")},
            )
        finally:
            await client.aclose()
        return response.status_code, response.json()

    return asyncio.run(run())
