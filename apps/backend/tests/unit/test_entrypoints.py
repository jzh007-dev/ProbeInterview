import pytest
from pydantic import ValidationError

from probeinterview.entrypoints import api, database_initializer, worker
from probeinterview.platform.foundation.infrastructure.settings import Settings


def test_api_factory_validates_settings_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROBEINTERVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("PROBEINTERVIEW_CELERY_BROKER_URL", raising=False)
    create_app = getattr(api, "create_app", None)
    assert create_app is not None, "API startup factory has not been implemented"

    with pytest.raises(ValidationError):
        create_app()


def test_worker_factory_validates_settings_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROBEINTERVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("PROBEINTERVIEW_CELERY_BROKER_URL", raising=False)
    create_celery_app = getattr(worker, "create_celery_app", None)
    assert create_celery_app is not None, "worker startup factory has not been implemented"

    with pytest.raises(ValidationError):
        create_celery_app()


def test_database_initializer_migrates_before_optional_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    config = type("Config", (), {"attributes": {}})()
    engine = type("Engine", (), {"dispose": lambda self: events.append("dispose")})()
    monkeypatch.setattr(database_initializer, "Config", lambda _: config)
    monkeypatch.setattr(
        database_initializer.command,
        "upgrade",
        lambda received_config, revision: events.append(
            ("upgrade", received_config.attributes["database_url"], revision)
        ),
    )
    monkeypatch.setattr(
        database_initializer,
        "create_engine",
        lambda database_url: events.append(("engine", database_url)) or engine,
    )
    monkeypatch.setattr(
        database_initializer,
        "seed_demo_profile",
        lambda received_engine: events.append(("seed", received_engine)),
    )

    database_initializer.initialize_database(make_initializer_settings(seed=True))

    assert events == [
        ("upgrade", "postgresql+psycopg://probe:probe@db/probe", "head"),
        ("engine", "postgresql+psycopg://probe:probe@db/probe"),
        ("seed", engine),
        "dispose",
    ]


def test_database_initializer_skips_demo_seed_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrades: list[str] = []
    config = type("Config", (), {"attributes": {}})()
    monkeypatch.setattr(database_initializer, "Config", lambda _: config)
    monkeypatch.setattr(
        database_initializer.command,
        "upgrade",
        lambda _config, revision: upgrades.append(revision),
    )
    monkeypatch.setattr(
        database_initializer,
        "create_engine",
        lambda _database_url: pytest.fail("seed engine must not be created"),
    )

    database_initializer.initialize_database(make_initializer_settings(seed=False))

    assert upgrades == ["head"]


def make_initializer_settings(*, seed: bool) -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        local_actor_enabled=False,
        demo_profile_seed_enabled=seed,
        _env_file=None,
    )
