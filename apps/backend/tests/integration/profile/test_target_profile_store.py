"""PostgreSQL serialization for concurrent first target profile writes."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from probeinterview.candidate.profile.application.target_profile import (
    TargetProfileWrite,
)
from probeinterview.candidate.profile.infrastructure.repository import (
    SqlAlchemyDefaultTargetProfileStore,
)
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def isolated_database_url() -> str:
    """Return only a database created by the destructive integration runner."""

    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/verify --full")
    if os.getenv("PROBEINTERVIEW_DESTRUCTIVE_DATABASE_TEST") != "1":
        raise RuntimeError("destructive database test sentinel is required")
    if "/probeinterview_profile_test_" not in database_url:
        raise RuntimeError("refusing to migrate a non-isolated database")
    return database_url


@pytest.fixture(scope="module")
def profile_engine() -> Engine:
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


def test_concurrent_first_writes_serialize_into_one_default_row(
    profile_engine: Engine,
) -> None:
    """Racing first writes for one actor converge on a single default row."""

    user_id = insert_user(profile_engine)
    store = SqlAlchemyDefaultTargetProfileStore(create_session_factory(profile_engine))
    roles = [f"并发角色 {index}" for index in range(8)]

    with ThreadPoolExecutor(max_workers=len(roles)) as executor:
        outcomes = list(
            executor.map(
                lambda role: store.upsert_default(
                    user_id,
                    TargetProfileWrite(
                        target_role=role,
                        relevant_experience_months=12,
                    ),
                ),
                roles,
            )
        )

    assert len({profile.id for profile in outcomes}) == 1
    with profile_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                select id, target_role, is_default
                from candidate_profiles
                where user_id = :user_id
                """
            ),
            {"user_id": user_id},
        ).all()
    assert len(rows) == 1
    assert rows[0][0] == outcomes[0].id
    assert rows[0][1] in roles
    assert rows[0][2] is True


def test_unique_default_index_backstops_the_actor_lock(
    profile_engine: Engine,
) -> None:
    """The partial unique index rejects a second default per actor outright."""

    user_id = insert_user(profile_engine)
    with profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:first_id, :user_id, '首个角色', 12, true)
                """
            ),
            {"first_id": uuid4(), "user_id": user_id},
        )
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:second_id, :user_id, '次级角色', 24, false)
                """
            ),
            {"second_id": uuid4(), "user_id": user_id},
        )

    with (
        pytest.raises(Exception, match="uq_candidate_profiles_default_per_user"),
        profile_engine.begin() as connection,
    ):
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:third_id, :user_id, '重复默认角色', 36, true)
                """
            ),
            {"third_id": uuid4(), "user_id": user_id},
        )


def insert_user(engine: Engine) -> UUID:
    """Insert one user and return its generated id."""

    user_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, '并发用户', null)
                """
            ),
            {"id": user_id},
        )
    return user_id
