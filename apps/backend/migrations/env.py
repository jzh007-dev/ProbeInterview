"""Alembic environment backed by the shared persistence infrastructure."""

from importlib import import_module
from logging.config import fileConfig

from alembic import context

from probeinterview.platform.foundation.infrastructure.persistence import (
    Base,
    create_engine,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

for model_module in (
    "probeinterview.identity.access.infrastructure.models",
    "probeinterview.candidate.profile.infrastructure.models",
):
    import_module(model_module)


def database_url() -> str:
    """Read URLs without ConfigParser interpolation of percent-encoded values."""

    attribute_url = config.attributes.get("database_url")
    if isinstance(attribute_url, str):
        return attribute_url

    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url is None:
        raise RuntimeError("Alembic requires a database URL")
    return configured_url


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with the shared SQLAlchemy engine configuration."""

    connectable = create_engine(database_url())

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
