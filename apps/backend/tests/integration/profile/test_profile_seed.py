"""Idempotent PostgreSQL seed coverage for the development profile."""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from probeinterview.entrypoints.profile_seed import (
    DEMO_PROFILE_ID,
    DEMO_USER_ID,
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


def scalar_count(engine: Engine, statement: str, values: dict[str, UUID]) -> int:
    """Return a count from the isolated seed database."""

    with engine.connect() as connection:
        return int(connection.execute(text(statement), values).scalar_one())


def test_demo_profile_seed_is_idempotent_and_contains_no_resume(
    profile_engine: Engine,
) -> None:
    seed_demo_profile(profile_engine)
    seed_demo_profile(profile_engine)

    user_values = {"user_id": DEMO_USER_ID}
    assert (
        scalar_count(
            profile_engine,
            "select count(*) from users where id = :user_id",
            user_values,
        )
        == 1
    )
    assert (
        scalar_count(
            profile_engine,
            "select count(*) from wechat_identities where user_id = :user_id",
            user_values,
        )
        == 1
    )
    assert (
        scalar_count(
            profile_engine,
            "select count(*) from candidate_profiles where user_id = :user_id",
            user_values,
        )
        >= 2
    )
    assert (
        scalar_count(
            profile_engine,
            """
        select count(*)
        from candidate_profiles
        where user_id = :user_id and is_default is true
        """,
            user_values,
        )
        == 1
    )
    assert (
        scalar_count(
            profile_engine,
            "select count(*) from user_resume where user_id = :user_id",
            user_values,
        )
        == 0
    )

    with profile_engine.connect() as connection:
        identity = connection.execute(
            text(
                """
                select app_id, openid, unionid
                from wechat_identities
                where user_id = :user_id
                """
            ),
            user_values,
        ).one()
        default_profile_id = connection.execute(
            text(
                """
                select id
                from candidate_profiles
                where user_id = :user_id and is_default is true
                """
            ),
            user_values,
        ).scalar_one()

    assert identity.app_id.startswith("wx")
    assert identity.openid
    assert identity.unionid
    assert default_profile_id == DEMO_PROFILE_ID
