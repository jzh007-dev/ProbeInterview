import pytest
from pydantic import ValidationError

from probeinterview.entrypoints import api, worker


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
