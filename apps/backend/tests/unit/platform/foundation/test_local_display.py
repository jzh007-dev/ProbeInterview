from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from starlette.testclient import TestClient

from probeinterview.entrypoints.api import create_app
from probeinterview.platform.foundation.infrastructure.settings import Settings


def make_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="display-test",
        fake_object_storage_display_base_url="http://127.0.0.1:8080",
        foundation_probe_enabled=False,
        _env_file=None,
    )


def store_avatar(app: object) -> tuple[str, str]:
    storage = app.state.object_storage  # type: ignore[attr-defined]
    content = b"fake-avatar-bytes"
    object_key = f"avatars/{uuid4()}/display.png"
    storage.put(
        object_key=object_key,
        content=content,
        content_type="image/png",
        checksum_sha256=sha256(content).hexdigest(),
    )
    signed = storage.sign_get_url(object_key=object_key)
    return signed.url, content


def test_local_display_serves_objects_within_the_signed_lifetime() -> None:
    app = create_app(make_settings(), readiness_checks={})
    client = TestClient(app)

    url, content = store_avatar(app)
    path_with_query = url.removeprefix("http://127.0.0.1:8080")

    response = client.get(path_with_query)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"


def test_local_display_rejects_missing_invalid_and_expired_signatures() -> None:
    app = create_app(make_settings(), readiness_checks={})
    client = TestClient(app)
    url, _content = store_avatar(app)
    path = url.removeprefix("http://127.0.0.1:8080").split("?")[0]

    missing = client.get(path)
    assert missing.status_code == 403

    malformed = client.get(path, params={"expires_at": "not-a-timestamp"})
    assert malformed.status_code == 403

    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    expired = client.get(path, params={"expires_at": expired_at.isoformat()})
    assert expired.status_code == 403

    unknown = client.get(
        "/local-objects/avatars/nobody/missing.png",
        params={"expires_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()},
    )
    assert unknown.status_code == 404


def test_local_display_route_is_absent_without_the_fake_adapter() -> None:
    """OSS-backed apps must not expose the fake-storage display surface."""

    settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@db/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="display-test",
        object_storage_adapter="oss",
        oss_endpoint="https://oss.example.invalid",
        oss_bucket="probeinterview",
        oss_access_key_id="test-key",
        oss_access_key_secret="test-secret",
        foundation_probe_enabled=False,
        _env_file=None,
    )
    app = create_app(settings, readiness_checks={})
    client = TestClient(app)

    response = client.get(
        "/local-objects/avatars/x/y.png",
        params={"expires_at": datetime.now(UTC).isoformat()},
    )
    assert response.status_code == 404
