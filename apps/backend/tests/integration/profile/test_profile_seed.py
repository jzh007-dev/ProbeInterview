"""Idempotent PostgreSQL seed coverage for the development profile."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from probeinterview.entrypoints.profile_seed import (
    DEMO_PROFILE_ID,
    DEMO_SECONDARY_PROFILE_ID,
    DEMO_USER_ID,
    DEMO_WECHAT_IDENTITY_ID,
    seed_demo_profile,
)
from probeinterview.platform.foundation.infrastructure.persistence import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[3]


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
def profile_engine() -> Iterator[Engine]:
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


def seed_snapshot(engine: Engine) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Capture every row owned by the deterministic seed user."""

    user_values = {"user_id": DEMO_USER_ID}
    statements = {
        "users": """
            select id, nickname, avatar_object_key
            from users
            where id = :user_id
            order by id
        """,
        "wechat_identities": """
            select id, user_id, app_id, openid, unionid
            from wechat_identities
            where user_id = :user_id
            order by id
        """,
        "candidate_profiles": """
            select id, user_id, target_role, relevant_experience_months, is_default
            from candidate_profiles
            where user_id = :user_id
            order by id
        """,
        "user_resume": """
            select id
            from user_resume
            where user_id = :user_id
            order by id
        """,
    }
    with engine.connect() as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(text(statement), user_values).all()
            )
            for table, statement in statements.items()
        }


def test_demo_profile_seed_is_idempotent_and_contains_no_resume(
    profile_engine: Engine,
) -> None:
    seed_demo_profile(profile_engine, wechat_app_id="seed-test-app-id")
    first_snapshot = seed_snapshot(profile_engine)

    assert first_snapshot == {
        "users": (
            (
                DEMO_USER_ID,
                "Bao",
                None,
            ),
        ),
        "wechat_identities": (
            (
                DEMO_WECHAT_IDENTITY_ID,
                DEMO_USER_ID,
                "seed-test-app-id",
                "oProbeInterviewDemoOpenId01",
                "uProbeInterviewDemoUnionId1",
            ),
        ),
        "candidate_profiles": (
            (
                DEMO_PROFILE_ID,
                DEMO_USER_ID,
                "AI 全栈开发",
                84,
                True,
            ),
            (
                DEMO_SECONDARY_PROFILE_ID,
                DEMO_USER_ID,
                "后端开发",
                60,
                False,
            ),
        ),
        "user_resume": (),
    }

    seed_demo_profile(profile_engine, wechat_app_id="seed-test-app-id")

    assert seed_snapshot(profile_engine) == first_snapshot


def test_demo_profile_seed_keeps_historic_app_id_without_wechat_settings(
    profile_engine: Engine,
) -> None:
    """local_test environments have no wechat_app_id and keep the legacy binding."""

    seed_demo_profile(profile_engine)

    snapshot = seed_snapshot(profile_engine)
    assert snapshot["wechat_identities"][0][2] == "wx8f3c2a1d9e7b6c5a"
