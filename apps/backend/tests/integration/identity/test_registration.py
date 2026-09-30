"""API-level acceptance for first registration against real persistence."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, text

from probeinterview.entrypoints.api import create_app
from probeinterview.entrypoints.identity_wiring import build_wechat_registration_service
from probeinterview.platform.foundation.infrastructure.object_storage import (
    FakeObjectStorage,
)
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ID = "wx-registration-app"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"avatar-payload"


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
def database(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


def make_client(database_url: str) -> AsyncClient:
    app = create_app(settings=make_settings(database_url), readiness_checks={})
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def request_registration_credential(
    database_url: str,
    openid: str,
) -> str:
    """Exchange one unknown identity into a live registration token."""

    client = make_client(database_url)
    try:
        response = await client.post("/api/v1/auth/wechat/exchanges", json={"code": openid})
    finally:
        await client.aclose()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "registration_required"
    return str(payload["registration_token"])


async def post_registration(
    database_url: str,
    registration_token: str,
    nickname: str,
) -> Response:
    """Post the JSON default-avatar registration route."""

    client = make_client(database_url)
    try:
        response = await client.post(
            "/api/v1/auth/wechat/registrations",
            json={"registration_token": registration_token, "nickname": nickname},
        )
    finally:
        await client.aclose()
    return response


async def post_avatar_registration(
    database_url: str,
    registration_token: str,
    nickname: str,
) -> Response:
    """Post the multipart custom-avatar registration route."""

    client = make_client(database_url)
    try:
        response = await client.post(
            "/api/v1/auth/wechat/avatar-registrations",
            data={"registration_token": registration_token, "nickname": nickname},
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )
    finally:
        await client.aclose()
    return response


def registration_state(database: Engine) -> dict[str, object]:
    """Capture users, bindings, sessions, attempts, and candidate profiles."""

    with database.connect() as connection:
        return {
            "users": connection.execute(
                text("select id, nickname, avatar_object_key from users")
            ).all(),
            "identities": connection.execute(
                text("select app_id, openid, user_id from wechat_identities")
            ).all(),
            "sessions": connection.execute(
                text("select user_id, revoked_at from auth_sessions")
            ).all(),
            "attempts": connection.execute(
                text("select consumed_at, resolved_user_id from wechat_registration_attempts")
            ).all(),
            "profiles": connection.execute(
                text("select count(*) from candidate_profiles")
            ).scalar(),
        }


@pytest.mark.asyncio
async def test_default_avatar_registration_creates_account_atomically(
    database_url: str,
    database: Engine,
) -> None:
    """Registration creates user, binding, session, and consumes the attempt."""

    openid = "oRegisterDefaultOpenId"
    registration_token = await request_registration_credential(database_url, openid)

    response = await post_registration(database_url, registration_token, "  新同学  ")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "authenticated"
    assert payload["current_user"] == {
        "id": payload["current_user"]["id"],
        "nickname": "新同学",
        "avatar_url": None,
        "avatar_url_expires_at": None,
        "default_target_profile": None,
    }

    state = registration_state(database)
    users = state["users"]
    assert isinstance(users, list) and len(users) == 1
    assert users[0][1] == "新同学"
    assert users[0][2] is None
    assert state["identities"] == [(APP_ID, openid, users[0][0])]
    assert len(state["sessions"]) == 1
    attempts = state["attempts"]
    assert isinstance(attempts, list) and len(attempts) == 1
    assert attempts[0][0] is not None
    assert attempts[0][1] == users[0][0]
    assert state["profiles"] == 0


@pytest.mark.asyncio
async def test_custom_avatar_registration_stores_private_object(
    database_url: str,
    database: Engine,
) -> None:
    """Custom avatars land under the private prefix with the object key stored."""

    openid = "oRegisterAvatarOpenId"
    registration_token = await request_registration_credential(database_url, openid)

    response = await post_avatar_registration(database_url, registration_token, "头像用户")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "authenticated"
    current_user = payload["current_user"]
    assert current_user["avatar_url"] is not None
    assert current_user["avatar_url_expires_at"] is not None
    assert "avatar_object_key" not in current_user

    with database.connect() as connection:
        avatar_key = connection.execute(text("select avatar_object_key from users")).scalar_one()
    assert avatar_key is not None
    assert str(avatar_key).startswith("avatars/")
    assert str(avatar_key).endswith(".png")


@pytest.mark.asyncio
async def test_unknown_expired_and_consumed_credentials_reject(
    database_url: str,
    database: Engine,
) -> None:
    """Unknown, expired, and unreconcilable consumed tokens all return 401."""

    for registration_token in ("totally-unknown",):
        response = await post_registration(database_url, registration_token, "某用户")
        assert response.status_code == 401
        assert response.json()["code"] == "registration_token_invalid"

    expired_openid = "oRegisterExpiredOpenId"
    expired_token = await request_registration_credential(database_url, expired_openid)
    with database.begin() as connection:
        connection.execute(
            text(
                """
                update wechat_registration_attempts
                set created_at = :created_at, expires_at = :expires_at
                """
            ),
            {
                "created_at": datetime.now(UTC) - timedelta(minutes=11),
                "expires_at": datetime.now(UTC) - timedelta(minutes=1),
            },
        )
    response = await post_registration(database_url, expired_token, "某用户")
    assert response.status_code == 401

    consumed_openid = "oRegisterConsumedOpenId"
    consumed_token = await request_registration_credential(database_url, consumed_openid)
    with database.begin() as connection:
        foreign_user = uuid4()
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, null)
                """
            ),
            {"id": foreign_user, "nickname": "外部用户"},
        )
        connection.execute(
            text(
                """
                update wechat_registration_attempts
                set consumed_at = now(), resolved_user_id = :foreign_user
                """
            ),
            {"foreign_user": foreign_user},
        )
        # The binding points at a different user than the consumed attempt,
        # so the credential cannot safely converge and must be rejected.
        binding_user = uuid4()
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, null)
                """
            ),
            {"id": binding_user, "nickname": "实际绑定用户"},
        )
        connection.execute(
            text(
                """
                insert into wechat_identities (id, user_id, app_id, openid, unionid)
                values (:id, :user_id, :app_id, :openid, null)
                """
            ),
            {
                "id": uuid4(),
                "user_id": binding_user,
                "app_id": APP_ID,
                "openid": consumed_openid,
            },
        )
    response = await post_registration(database_url, consumed_token, "某用户")
    assert response.status_code == 401
    assert response.json()["code"] == "registration_token_invalid"


@pytest.mark.asyncio
async def test_invalid_nickname_returns_field_problem(
    database_url: str,
    database: Engine,
) -> None:
    """Nickname validation rejects before any user state is created."""

    registration_token = await request_registration_credential(
        database_url, "oRegisterInvalidNickname"
    )

    response = await post_registration(database_url, registration_token, "bad\x00name")
    assert response.status_code == 422
    problem = response.json()
    assert problem["code"] == "invalid_nickname"
    assert problem["errors"][0]["field"] == "nickname"

    state = registration_state(database)
    assert state["users"] == []


@pytest.mark.asyncio
async def test_invalid_avatar_returns_field_problem(
    database_url: str,
    database: Engine,
) -> None:
    """Magic-byte mismatch rejects before any user state is created."""

    registration_token = await request_registration_credential(
        database_url, "oRegisterInvalidAvatar"
    )

    client = make_client(database_url)
    try:
        response = await client.post(
            "/api/v1/auth/wechat/avatar-registrations",
            data={"registration_token": registration_token, "nickname": "某用户"},
            files={"file": ("fake.png", b"GIF89a-not-a-png", "image/png")},
        )
    finally:
        await client.aclose()
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_avatar"
    assert registration_state(database)["users"] == []


@pytest.mark.asyncio
async def test_storage_failure_leaves_no_account_state(
    database_url: str,
    database: Engine,
) -> None:
    """An avatar upload failure rolls back user, binding, and session state."""

    registration_token = await request_registration_credential(database_url, "oRegisterStorageFail")

    app_storage = FakeObjectStorage(fail_put=True)
    app = create_app(settings=make_settings(database_url), readiness_checks={})
    app.state.wechat_registration_service = build_wechat_registration_service(
        create_session_factory(database), app_storage
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    try:
        response = await client.post(
            "/api/v1/auth/wechat/avatar-registrations",
            data={"registration_token": registration_token, "nickname": "某用户"},
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )
    finally:
        await client.aclose()

    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"
    state = registration_state(database)
    assert state["users"] == []
    assert state["identities"] == []
    assert state["sessions"] == []
    assert app_storage.calls[0].operation == "put"
