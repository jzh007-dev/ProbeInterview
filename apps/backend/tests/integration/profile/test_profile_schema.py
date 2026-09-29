"""PostgreSQL constraints for persisted profile overview data."""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

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


def insert_user(engine: Engine, user_id: UUID | None = None) -> UUID:
    """Insert one display user for constraint setup."""

    resolved_user_id = user_id or uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_url)
                values (:id, :nickname, :avatar_url)
                """
            ),
            {
                "id": resolved_user_id,
                "nickname": f"user-{resolved_user_id}",
                "avatar_url": "https://example.invalid/avatar.png",
            },
        )
    return resolved_user_id


def valid_resume_values(user_id: UUID) -> dict[str, object]:
    """Return independently specified valid metadata for one current resume."""

    resume_id = uuid4()
    return {
        "id": resume_id,
        "user_id": user_id,
        "original_file_name": "resume.pdf",
        "media_type": "application/pdf",
        "size_bytes": 1024,
        "content_sha256": "a" * 64,
        "storage_object_key": f"resumes/{user_id}/{resume_id}/1.pdf",
        "revision": 1,
    }


def insert_resume(engine: Engine, values: dict[str, object]) -> None:
    """Insert current-resume metadata using the complete storage-neutral contract."""

    with engine.begin() as connection:
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
                    uploaded_at
                )
                values (
                    :id,
                    :user_id,
                    :original_file_name,
                    :media_type,
                    :size_bytes,
                    :content_sha256,
                    :storage_object_key,
                    :revision,
                    now()
                )
                """
            ),
            values,
        )


def test_profile_schema_contains_only_expected_tables_and_columns(
    profile_engine: Engine,
) -> None:
    """Schema drift must not add private bytes, identity secrets, or provider fields."""

    inspector = inspect(profile_engine)
    assert {"users", "wechat_identities", "candidate_profiles", "user_resume"}.issubset(
        inspector.get_table_names()
    )
    assert {column["name"] for column in inspector.get_columns("wechat_identities")} == {
        "id",
        "user_id",
        "app_id",
        "openid",
        "unionid",
        "created_at",
        "updated_at",
    }
    assert {column["name"] for column in inspector.get_columns("user_resume")} == {
        "id",
        "user_id",
        "original_file_name",
        "media_type",
        "size_bytes",
        "content_sha256",
        "storage_object_key",
        "revision",
        "uploaded_at",
        "updated_at",
    }


@pytest.mark.parametrize("owned_table", ["wechat_identities", "candidate_profiles", "user_resume"])
def test_owned_tables_reject_missing_users(profile_engine: Engine, owned_table: str) -> None:
    """Every identity/profile record must retain its restrictive user foreign key."""

    missing_user = uuid4()
    statements = {
        "wechat_identities": (
            """
            insert into wechat_identities (id, user_id, app_id, openid)
            values (:id, :user_id, 'wx-test-app', 'openid-test')
            """,
            {"id": uuid4(), "user_id": missing_user},
        ),
        "candidate_profiles": (
            """
            insert into candidate_profiles (
                id, user_id, target_role, relevant_experience_months, is_default
            )
            values (:id, :user_id, 'Backend Engineer', 12, false)
            """,
            {"id": uuid4(), "user_id": missing_user},
        ),
        "user_resume": (
            """
            insert into user_resume (
                id, user_id, original_file_name, media_type, size_bytes,
                content_sha256, storage_object_key, revision, uploaded_at
            )
            values (
                :id, :user_id, 'resume.pdf', 'application/pdf', 1,
                :content_sha256, :storage_object_key, 1, now()
            )
            """,
            {
                "id": uuid4(),
                "user_id": missing_user,
                "content_sha256": "b" * 64,
                "storage_object_key": f"resumes/{missing_user}/missing/1.pdf",
            },
        ),
    }

    statement, parameters = statements[owned_table]
    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(text(statement), parameters)


def test_wechat_app_and_openid_pair_is_unique(profile_engine: Engine) -> None:
    """Two identity rows must not claim the same WeChat app/openid pair."""

    first_user = insert_user(profile_engine)
    second_user = insert_user(profile_engine)
    with profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into wechat_identities (id, user_id, app_id, openid)
                values (:id, :user_id, 'wx-app', 'same-openid')
                """
            ),
            {"id": uuid4(), "user_id": first_user},
        )

    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into wechat_identities (id, user_id, app_id, openid)
                values (:id, :user_id, 'wx-app', 'same-openid')
                """
            ),
            {"id": uuid4(), "user_id": second_user},
        )


def test_profiles_require_non_negative_experience_and_one_default(
    profile_engine: Engine,
) -> None:
    """Experience and explicit-default invariants must be database enforced."""

    negative_user = insert_user(profile_engine)
    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:id, :user_id, 'Backend Engineer', -1, false)
                """
            ),
            {"id": uuid4(), "user_id": negative_user},
        )

    default_user = insert_user(profile_engine)
    with profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:id, :user_id, 'Backend Engineer', 24, true)
                """
            ),
            {"id": uuid4(), "user_id": default_user},
        )

    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id, user_id, target_role, relevant_experience_months, is_default
                )
                values (:id, :user_id, 'Platform Engineer', 36, true)
                """
            ),
            {"id": uuid4(), "user_id": default_user},
        )


def test_resume_is_single_current_row_per_user(profile_engine: Engine) -> None:
    """A user must not have two mutable current-resume rows."""

    user_id = insert_user(profile_engine)
    insert_resume(profile_engine, valid_resume_values(user_id))

    with pytest.raises(IntegrityError):
        insert_resume(profile_engine, valid_resume_values(user_id))


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("size_bytes", -1),
        ("content_sha256", "short"),
        ("storage_object_key", "   "),
        ("revision", 0),
    ],
)
def test_resume_metadata_constraints(
    profile_engine: Engine,
    field: str,
    invalid_value: object,
) -> None:
    """Each invalid metadata mutation must be rejected by PostgreSQL."""

    user_id = insert_user(profile_engine)
    values = valid_resume_values(user_id)
    values[field] = invalid_value

    with pytest.raises(IntegrityError):
        insert_resume(profile_engine, values)
