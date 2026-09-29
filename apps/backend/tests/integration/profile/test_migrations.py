"""PostgreSQL migration smoke tests for the profile vertical slice."""

import os
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, make_url, text

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SMOKE_VERSION_LOCATION = Path(__file__).with_name("migration_versions")


def require_test_database_url() -> str:
    """Require the isolated runner instead of an ambient developer database."""

    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/test-profile-postgres")
    if os.getenv("PROBEINTERVIEW_DESTRUCTIVE_DATABASE_TEST") != "1":
        raise RuntimeError("destructive database test sentinel is required")
    database_name = make_url(database_url).database
    if database_name is None or not database_name.startswith("probeinterview_profile_test_"):
        raise RuntimeError("refusing to migrate a non-isolated database")
    return database_url


def test_clean_database_upgrades_to_head_and_downgrades_to_base() -> None:
    """A clean PostgreSQL database must support the full migration lifecycle."""

    database_url = require_test_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    config.set_main_option("version_locations", str(SMOKE_VERSION_LOCATION))

    command.upgrade(config, "head")
    persistence = import_module("probeinterview.platform.foundation.infrastructure.persistence")
    engine = persistence.create_engine(database_url)
    assert "profile_migration_smoke" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == (
            "0001_profile_smoke"
        )

    command.downgrade(config, "base")
    assert "profile_migration_smoke" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from alembic_version")) == 0
    engine.dispose()


def test_shared_session_factory_connects_to_postgresql() -> None:
    """The shared persistence boundary must create usable SQLAlchemy sessions."""

    module_name = "probeinterview.platform.foundation.infrastructure.persistence"
    assert find_spec(module_name) is not None
    persistence = import_module(module_name)

    engine = persistence.create_engine(require_test_database_url())
    session_factory = persistence.create_session_factory(engine)

    with session_factory() as session:
        assert session.scalar(text("select 1")) == 1

    engine.dispose()
