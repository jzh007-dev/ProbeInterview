"""PostgreSQL-backed acceptance coverage for the owner-scoped overview API."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, text

from probeinterview.entrypoints.api import create_app
from probeinterview.entrypoints.profile_seed import DEMO_USER_ID, seed_demo_profile
from probeinterview.platform.foundation.infrastructure.persistence import create_engine
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.asyncio

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SECOND_ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e3001")
SECOND_PROFILE_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e3002")
SECOND_RESUME_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e3003")
INCOMPLETE_ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e4001")


def isolated_database_url() -> str:
    """Return only a database created by the destructive integration runner."""

    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/test-profile-postgres")
    if os.getenv("PROBEINTERVIEW_DESTRUCTIVE_DATABASE_TEST") != "1":
        raise RuntimeError("destructive database test sentinel is required")
    if "/probeinterview_profile_test_" not in database_url:
        raise RuntimeError("refusing to migrate a non-isolated database")
    return database_url


@pytest.fixture(scope="module")
def profile_database() -> Iterator[tuple[str, Engine]]:
    """Migrate one isolated database and populate all overview fixtures."""

    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    seed_demo_profile(engine)
    insert_profile_fixtures(engine)
    try:
        yield database_url, engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


async def test_unresolved_actor_returns_401_problem_details(
    profile_database: tuple[str, Engine],
) -> None:
    async with client_without_actor(profile_database[0]) as client:
        response = await client.get(
            "/api/v1/me/overview",
            headers={"X-Request-ID": "missing-actor"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "A current actor is required.",
        "instance": "/api/v1/me/overview",
        "code": "actor_required",
        "request_id": "missing-actor",
    }


async def test_configured_actor_ignores_arbitrary_actor_header_and_returns_seed_overview(
    profile_database: tuple[str, Engine],
) -> None:
    async with client_for_actor(profile_database[0], DEMO_USER_ID) as client:
        response = await client.get(
            "/api/v1/me/overview",
            headers={"X-Actor-ID": str(SECOND_ACTOR_ID)},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(DEMO_USER_ID),
        "nickname": "Bao",
        "avatar_url": "https://example.invalid/avatars/bao.png",
        "default_target_profile": {
            "id": "018f7f64-3c6a-7d21-95a8-4d1b8c2e2001",
            "target_role": "AI 全栈开发",
            "relevant_experience_months": 84,
        },
        "current_resume": None,
        "recent_scores": [],
    }


async def test_resume_response_is_display_safe_and_uses_explicit_default(
    profile_database: tuple[str, Engine],
) -> None:
    async with client_for_actor(profile_database[0], SECOND_ACTOR_ID) as client:
        response = await client.get("/api/v1/me/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(SECOND_ACTOR_ID)
    assert body["nickname"] == "Second Actor"
    assert body["default_target_profile"] == {
        "id": str(SECOND_PROFILE_ID),
        "target_role": "Platform Engineer",
        "relevant_experience_months": 48,
    }
    assert body["recent_scores"] == []
    assert body["current_resume"] == {
        "id": str(SECOND_RESUME_ID),
        "original_file_name": "second-resume.pdf",
        "media_type": "application/pdf",
        "size_bytes": 2048,
        "revision": 3,
        "uploaded_at": "2026-09-29T08:00:00Z",
        "updated_at": "2026-09-29T08:05:00Z",
    }
    forbidden_keys = {
        "storage_object_key",
        "content_sha256",
        "url",
        "provider",
        "app_id",
        "openid",
        "unionid",
    }
    assert forbidden_keys.isdisjoint(body["current_resume"])
    assert {"app_id", "openid", "unionid"}.isdisjoint(body)


async def test_two_configured_apps_do_not_cross_actor_boundaries(
    profile_database: tuple[str, Engine],
) -> None:
    async with (
        client_for_actor(profile_database[0], DEMO_USER_ID) as first_client,
        client_for_actor(profile_database[0], SECOND_ACTOR_ID) as second_client,
    ):
        first_response = await first_client.get("/api/v1/me/overview")
        second_response = await second_client.get("/api/v1/me/overview")

    assert first_response.json()["nickname"] == "Bao"
    assert first_response.json()["current_resume"] is None
    assert second_response.json()["nickname"] == "Second Actor"
    assert second_response.json()["current_resume"]["id"] == str(SECOND_RESUME_ID)
    assert "second-resume.pdf" not in first_response.text
    assert "AI 全栈开发" not in second_response.text


async def test_missing_default_profile_returns_409_problem_details(
    profile_database: tuple[str, Engine],
) -> None:
    async with client_for_actor(profile_database[0], INCOMPLETE_ACTOR_ID) as client:
        response = await client.get(
            "/api/v1/me/overview",
            headers={"X-Request-ID": "incomplete-profile"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Profile Overview Incomplete",
        "status": 409,
        "detail": "The current actor has no default target profile.",
        "instance": "/api/v1/me/overview",
        "code": "profile_overview_incomplete",
        "request_id": "incomplete-profile",
    }


def client_for_actor(database_url: str, actor_id: UUID) -> AsyncClient:
    settings = make_settings(
        database_url,
        authentication_mode="local_test",
        local_actor_id=actor_id,
    )
    app = create_app(settings=settings, readiness_checks={})
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def client_without_actor(database_url: str) -> AsyncClient:
    settings = make_settings(
        database_url,
        authentication_mode="wechat",
        local_actor_id=None,
    )
    app = create_app(settings=settings, readiness_checks={})
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def make_settings(
    database_url: str,
    *,
    authentication_mode: str,
    local_actor_id: UUID | None,
) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        celery_broker_url="redis://redis:6379/0",
        authentication_mode=authentication_mode,
        local_actor_id=local_actor_id,
        wechat_app_id=("profile-integration" if authentication_mode == "wechat" else None),
        foundation_probe_enabled=False,
        _env_file=None,
    )


def insert_profile_fixtures(engine: Engine) -> None:
    uploaded_at = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
    updated_at = datetime(2026, 9, 29, 8, 5, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_url)
                values
                    (:second_id, 'Second Actor', 'https://example.invalid/second.png'),
                    (:incomplete_id, 'Incomplete Actor', 'https://example.invalid/incomplete.png')
                """
            ),
            {
                "second_id": SECOND_ACTOR_ID,
                "incomplete_id": INCOMPLETE_ACTOR_ID,
            },
        )
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values
                    (
                        :second_profile_id,
                        :second_id,
                        'Platform Engineer',
                        48,
                        true
                    ),
                    (
                        :second_other_profile_id,
                        :second_id,
                        'Wrong Non Default Role',
                        120,
                        false
                    ),
                    (
                        :incomplete_profile_id,
                        :incomplete_id,
                        'No Default Role',
                        12,
                        false
                    )
                """
            ),
            {
                "second_profile_id": SECOND_PROFILE_ID,
                "second_other_profile_id": UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e3004"),
                "incomplete_profile_id": UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e4002"),
                "second_id": SECOND_ACTOR_ID,
                "incomplete_id": INCOMPLETE_ACTOR_ID,
            },
        )
        connection.execute(
            text(
                """
                insert into user_resume (
                    id,
                    user_id,
                    original_file_name,
                    media_type,
                    size_bytes,
                    content_sha256,
                    storage_object_key,
                    revision,
                    uploaded_at,
                    updated_at
                )
                values (
                    :id,
                    :user_id,
                    'second-resume.pdf',
                    'application/pdf',
                    2048,
                    :content_sha256,
                    :storage_object_key,
                    3,
                    :uploaded_at,
                    :updated_at
                )
                """
            ),
            {
                "id": SECOND_RESUME_ID,
                "user_id": SECOND_ACTOR_ID,
                "content_sha256": "c" * 64,
                "storage_object_key": (f"resumes/{SECOND_ACTOR_ID}/{SECOND_RESUME_ID}/3.pdf"),
                "uploaded_at": uploaded_at,
                "updated_at": updated_at,
            },
        )
