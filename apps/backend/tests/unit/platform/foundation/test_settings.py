from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from probeinterview.platform.foundation import infrastructure


def settings_type() -> Callable[..., Any]:
    settings = getattr(infrastructure, "Settings", None)
    assert settings is not None, "foundation Settings has not been implemented"
    return settings


def production_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://probe:probe@db/probe",
        "celery_broker_url": "redis://redis:6379/0",
        "authentication_mode": "wechat",
        "local_actor_id": None,
        "wechat_adapter": "real",
        "wechat_app_id": "production-app-id",
        "wechat_app_secret": "production-app-secret",
        "demo_profile_seed_enabled": False,
        "foundation_probe_enabled": False,
        "object_storage_adapter": "oss",
        "embedding_adapter": "bailian",
        "structured_llm_adapter": "bailian",
        "oss_endpoint": "https://oss.example.invalid",
        "oss_bucket": "probeinterview",
        "oss_access_key_id": "test-access-key",
        "oss_access_key_secret": "test-access-secret",
        "bailian_api_key": "test-bailian-key",
    }
    values.update(overrides)
    return values


def test_missing_required_connections_fail_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROBEINTERVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("PROBEINTERVIEW_CELERY_BROKER_URL", raising=False)

    with pytest.raises(ValidationError) as error:
        settings_type()(_env_file=None)

    missing_fields = {tuple(item["loc"]) for item in error.value.errors()}
    assert ("database_url",) in missing_fields
    assert ("celery_broker_url",) in missing_fields


def test_development_example_uses_wechat_fakes_without_secrets() -> None:
    example_path = Path(__file__).parents[4] / ".env.example"

    settings = settings_type()(_env_file=example_path)

    assert settings.environment == "development"
    assert settings.authentication_mode == "wechat"
    assert settings.local_actor_id is None
    assert settings.wechat_adapter == "fake"
    assert settings.wechat_app_id == "probeinterview-development"
    assert settings.wechat_app_secret is None
    assert settings.demo_profile_seed_enabled is True
    assert settings.foundation_probe_enabled is True
    assert settings.object_storage_adapter == "fake"
    assert settings.embedding_adapter == "fake"
    assert settings.structured_llm_adapter == "fake"
    assert settings.oss_access_key_secret is None
    assert settings.bailian_api_key is None


def test_production_rejects_local_actor() -> None:
    with pytest.raises(ValidationError, match="production forbids local_test authentication"):
        settings_type()(
            **production_values(
                authentication_mode="local_test",
                local_actor_id="018f7f64-3c6a-7d21-95a8-4d1b8c2e1001",
                wechat_app_id=None,
                wechat_app_secret=None,
            ),
            _env_file=None,
        )


def test_local_actor_id_is_typed_as_uuid() -> None:
    settings = settings_type()(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="local_test",
        local_actor_id="018f7f64-3c6a-7d21-95a8-4d1b8c2e1001",
        _env_file=None,
    )

    assert settings.local_actor_id == UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")


def test_local_test_authentication_requires_actor_id() -> None:
    with pytest.raises(ValidationError, match="local_test authentication requires local_actor_id"):
        settings_type()(
            environment="test",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="local_test",
            local_actor_id=None,
            _env_file=None,
        )


def test_wechat_authentication_rejects_local_actor_id() -> None:
    with pytest.raises(ValidationError, match="wechat authentication forbids local_actor_id"):
        settings_type()(
            environment="test",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="wechat",
            local_actor_id="018f7f64-3c6a-7d21-95a8-4d1b8c2e1001",
            wechat_adapter="fake",
            wechat_app_id="test-app",
            _env_file=None,
        )


def test_local_test_authentication_rejects_wechat_provider_fields() -> None:
    with pytest.raises(ValidationError, match="local_test authentication forbids WeChat settings"):
        settings_type()(
            environment="test",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="local_test",
            local_actor_id="018f7f64-3c6a-7d21-95a8-4d1b8c2e1001",
            wechat_app_id="conflicting-app",
            _env_file=None,
        )


def test_local_test_authentication_is_test_only() -> None:
    with pytest.raises(
        ValidationError,
        match="local_test authentication requires test environment",
    ):
        settings_type()(
            environment="development",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="local_test",
            local_actor_id="018f7f64-3c6a-7d21-95a8-4d1b8c2e1001",
            _env_file=None,
        )


@pytest.mark.parametrize("missing_field", ["wechat_app_id", "wechat_app_secret"])
def test_real_wechat_adapter_requires_server_credentials(missing_field: str) -> None:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": "postgresql+psycopg://probe:probe@db/probe",
        "celery_broker_url": "redis://redis:6379/0",
        "authentication_mode": "wechat",
        "wechat_adapter": "real",
        "wechat_app_id": "test-app",
        "wechat_app_secret": "test-secret",
    }
    values.pop(missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        settings_type()(**values, _env_file=None)


def test_fake_wechat_adapter_requires_app_id_but_rejects_app_secret() -> None:
    with pytest.raises(ValidationError, match="wechat_app_id"):
        settings_type()(
            environment="test",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="wechat",
            wechat_adapter="fake",
            _env_file=None,
        )

    with pytest.raises(ValidationError, match="fake WeChat adapter forbids wechat_app_secret"):
        settings_type()(
            environment="test",
            database_url="postgresql+psycopg://probe:probe@db/probe",
            celery_broker_url="redis://redis:6379/0",
            authentication_mode="wechat",
            wechat_adapter="fake",
            wechat_app_id="test-app",
            wechat_app_secret="must-not-be-used",
            _env_file=None,
        )


def test_production_rejects_demo_profile_seed() -> None:
    with pytest.raises(ValidationError, match="production forbids demo profile seed"):
        settings_type()(
            **production_values(demo_profile_seed_enabled=True),
            _env_file=None,
        )


def test_production_rejects_fake_adapter_fallback() -> None:
    with pytest.raises(ValidationError, match="production forbids fake adapters"):
        settings_type()(
            **production_values(object_storage_adapter="fake"),
            _env_file=None,
        )


def test_production_rejects_fake_wechat_adapter() -> None:
    with pytest.raises(ValidationError, match="production requires real WeChat adapter"):
        settings_type()(
            **production_values(
                wechat_adapter="fake",
                wechat_app_secret=None,
            ),
            _env_file=None,
        )


def test_production_rejects_foundation_probe() -> None:
    with pytest.raises(ValidationError, match="production forbids foundation probe"):
        settings_type()(
            **production_values(foundation_probe_enabled=True),
            _env_file=None,
        )


def test_production_real_adapters_require_credentials() -> None:
    values = production_values()
    for key in (
        "oss_endpoint",
        "oss_bucket",
        "oss_access_key_id",
        "oss_access_key_secret",
        "bailian_api_key",
    ):
        values.pop(key)

    with pytest.raises(ValidationError, match="missing production adapter settings"):
        settings_type()(**values, _env_file=None)


@pytest.mark.parametrize(
    ("field_name", "blank_value"),
    [
        ("oss_endpoint", ""),
        ("oss_bucket", "   "),
        ("oss_access_key_id", ""),
        ("oss_access_key_secret", " "),
        ("bailian_api_key", ""),
    ],
)
def test_production_rejects_blank_adapter_settings(
    field_name: str,
    blank_value: str,
) -> None:
    with pytest.raises(ValidationError, match=field_name):
        settings_type()(
            **production_values(**{field_name: blank_value}),
            _env_file=None,
        )
