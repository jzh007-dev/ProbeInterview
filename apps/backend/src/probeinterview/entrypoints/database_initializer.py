"""One-shot database migration and optional development seed entrypoint."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from probeinterview.entrypoints.profile_seed import seed_demo_profile
from probeinterview.platform.foundation.infrastructure.persistence import create_engine
from probeinterview.platform.foundation.infrastructure.settings import Settings


def initialize_database(
    settings: Settings,
    *,
    alembic_config_path: Path = Path("alembic.ini"),
) -> None:
    """Upgrade the configured database, then seed it only when explicitly enabled."""

    config = Config(str(alembic_config_path))
    config.attributes["database_url"] = settings.database_url
    command.upgrade(config, "head")

    if not settings.demo_profile_seed_enabled:
        return

    engine = create_engine(settings.database_url)
    try:
        seed_demo_profile(engine)
    finally:
        engine.dispose()


def main() -> None:
    """Initialize the database from validated process settings."""

    initialize_database(Settings())


if __name__ == "__main__":
    main()
