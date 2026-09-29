"""PostgreSQL migration smoke tests for the profile vertical slice."""

import os
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def require_test_database_url() -> str:
    """Require the isolated runner instead of an ambient developer database."""

    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/test-profile-postgres")
    return database_url


def test_clean_database_upgrades_to_head_and_downgrades_to_base() -> None:
    """A clean PostgreSQL database must support the full migration lifecycle."""

    database_url = require_test_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")


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
