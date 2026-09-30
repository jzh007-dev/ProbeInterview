"""PostgreSQL constraints for persisted profile overview data."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
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
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, :avatar_object_key)
                """
            ),
            {
                "id": resolved_user_id,
                "nickname": f"user-{resolved_user_id}",
                "avatar_object_key": f"avatars/{resolved_user_id}/default.png",
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
    resume_columns = {column["name"]: column for column in inspector.get_columns("user_resume")}
    assert set(resume_columns) == {
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
    assert resume_columns["uploaded_at"]["nullable"] is False
    assert resume_columns["uploaded_at"]["type"].timezone is True
    assert resume_columns["updated_at"]["nullable"] is False
    assert resume_columns["updated_at"]["type"].timezone is True
    assert resume_columns["updated_at"]["default"] is not None


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


@pytest.mark.parametrize("owned_table", ["wechat_identities", "candidate_profiles", "user_resume"])
def test_owned_tables_restrict_user_deletion(
    profile_engine: Engine,
    owned_table: str,
) -> None:
    """Changing an owned foreign key to cascade must break this test."""

    user_id = insert_user(profile_engine)
    if owned_table == "wechat_identities":
        with profile_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    insert into wechat_identities (id, user_id, app_id, openid)
                    values (:id, :user_id, :app_id, :openid)
                    """
                ),
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "app_id": f"wx-{user_id}",
                    "openid": f"openid-{user_id}",
                },
            )
    elif owned_table == "candidate_profiles":
        with profile_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    insert into candidate_profiles (
                        id, user_id, target_role, relevant_experience_months, is_default
                    )
                    values (:id, :user_id, 'Backend Engineer', 12, false)
                    """
                ),
                {"id": uuid4(), "user_id": user_id},
            )
    else:
        insert_resume(profile_engine, valid_resume_values(user_id))

    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(text("delete from users where id = :id"), {"id": user_id})


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


def test_resume_storage_object_key_is_unique(profile_engine: Engine) -> None:
    """Two users must not claim the same logical stored object."""

    first_user = insert_user(profile_engine)
    first_values = valid_resume_values(first_user)
    insert_resume(profile_engine, first_values)

    second_user = insert_user(profile_engine)
    second_values = valid_resume_values(second_user)
    second_values["storage_object_key"] = first_values["storage_object_key"]

    with pytest.raises(IntegrityError):
        insert_resume(profile_engine, second_values)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("size_bytes", -1),
        ("content_sha256", "short"),
        ("content_sha256", "g" * 64),
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


def test_users_replace_avatar_url_with_nullable_object_key(
    profile_engine: Engine,
) -> None:
    """Avatar truth is a unique, non-blank, nullable provider-neutral key."""

    inspector = inspect(profile_engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "avatar_url" not in user_columns
    assert "avatar_object_key" in user_columns

    first_user = insert_user(profile_engine)
    insert_user(profile_engine)

    with profile_engine.connect() as connection:
        stored_keys = (
            connection.execute(text("select avatar_object_key from users order by id"))
            .scalars()
            .all()
        )
    assert all(key is not None for key in stored_keys)

    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                    insert into users (id, nickname, avatar_object_key)
                    values (:id, :nickname, :avatar_object_key)
                    """
            ),
            {
                "id": uuid4(),
                "nickname": "duplicate-avatar",
                "avatar_object_key": f"avatars/{first_user}/default.png",
            },
        )

    with pytest.raises(IntegrityError), profile_engine.begin() as connection:
        connection.execute(
            text(
                """
                    insert into users (id, nickname, avatar_object_key)
                    values (:id, :nickname, :avatar_object_key)
                    """
            ),
            {
                "id": uuid4(),
                "nickname": "blank-avatar",
                "avatar_object_key": "   ",
            },
        )


def insert_registration_attempt(
    engine: Engine,
    values: dict[str, object],
) -> None:
    """Insert one registration attempt using explicit timestamps."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into wechat_registration_attempts (
                    id,
                    token_digest,
                    app_id,
                    openid,
                    unionid,
                    created_at,
                    expires_at,
                    consumed_at
                )
                values (
                    :id,
                    :token_digest,
                    :app_id,
                    :openid,
                    :unionid,
                    :created_at,
                    :expires_at,
                    :consumed_at
                )
                """
            ),
            values,
        )


def valid_attempt_values() -> dict[str, object]:
    """Return independently specified valid registration attempt metadata."""

    return {
        "id": uuid4(),
        "token_digest": "b" * 64,
        "app_id": "wx8f3c2a1d9e7b6c5a",
        "openid": "oProbeInterviewSchemaOpenId",
        "unionid": None,
        "created_at": datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
        "expires_at": datetime(2026, 10, 1, 8, 10, tzinfo=UTC),
        "consumed_at": None,
    }


def test_registration_attempt_constraints(
    profile_engine: Engine,
) -> None:
    """Attempts persist digest-only credentials with strict expiry bounds."""

    inspector = inspect(profile_engine)
    assert {column["name"] for column in inspector.get_columns("wechat_registration_attempts")} == {
        "id",
        "token_digest",
        "app_id",
        "openid",
        "unionid",
        "resolved_user_id",
        "created_at",
        "expires_at",
        "consumed_at",
    }

    insert_registration_attempt(profile_engine, valid_attempt_values())

    duplicate_values = valid_attempt_values()
    duplicate_values["id"] = uuid4()
    with pytest.raises(IntegrityError):
        insert_registration_attempt(profile_engine, duplicate_values)

    for _, invalid_value in (
        ("token_digest", "short"),
        ("token_digest", "g" * 64),
    ):
        invalid_values = valid_attempt_values()
        invalid_values["id"] = uuid4()
        invalid_values["token_digest"] = invalid_value
        with pytest.raises(IntegrityError):
            insert_registration_attempt(profile_engine, invalid_values)

    expired_values = valid_attempt_values()
    expired_values["id"] = uuid4()
    expired_values["expires_at"] = expired_values["created_at"]
    with pytest.raises(IntegrityError):
        insert_registration_attempt(profile_engine, expired_values)


def insert_auth_session(engine: Engine, values: dict[str, object]) -> None:
    """Insert one auth session using explicit timestamps."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into auth_sessions (
                    id,
                    user_id,
                    token_digest,
                    created_at,
                    expires_at,
                    revoked_at
                )
                values (
                    :id,
                    :user_id,
                    :token_digest,
                    :created_at,
                    :expires_at,
                    :revoked_at
                )
                """
            ),
            values,
        )


def valid_session_values(user_id: UUID) -> dict[str, object]:
    """Return independently specified valid session metadata."""

    return {
        "id": uuid4(),
        "user_id": user_id,
        "token_digest": "c" * 64,
        "created_at": datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
        "expires_at": datetime(2026, 10, 31, 8, 0, tzinfo=UTC),
        "revoked_at": None,
    }


def test_auth_session_constraints(
    profile_engine: Engine,
) -> None:
    """Sessions persist digest-only tokens with expiry and revocation truth."""

    user_id = insert_user(profile_engine)
    insert_auth_session(profile_engine, valid_session_values(user_id))

    duplicate_values = valid_session_values(user_id)
    duplicate_values["id"] = uuid4()
    with pytest.raises(IntegrityError):
        insert_auth_session(profile_engine, duplicate_values)

    for _, invalid_value in (
        ("token_digest", "short"),
        ("token_digest", "z" * 64),
    ):
        invalid_values = valid_session_values(user_id)
        invalid_values["id"] = uuid4()
        invalid_values["token_digest"] = invalid_value
        with pytest.raises(IntegrityError):
            insert_auth_session(profile_engine, invalid_values)

    expired_values = valid_session_values(user_id)
    expired_values["id"] = uuid4()
    expired_values["expires_at"] = expired_values["created_at"]
    with pytest.raises(IntegrityError):
        insert_auth_session(profile_engine, expired_values)

    revoked_values = valid_session_values(user_id)
    revoked_values["id"] = uuid4()
    revoked_values["token_digest"] = "d" * 64
    revoked_values["revoked_at"] = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    insert_auth_session(profile_engine, revoked_values)
