"""Opt-in write/delete smoke test for the manually provisioned OSS bucket."""

import os
from hashlib import sha256
from uuid import uuid4

import pytest

from probeinterview.platform.foundation.infrastructure.object_storage import OssObjectStorage
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.oss_smoke


def test_oss_write_and_delete_unique_private_object() -> None:
    required = (
        "PROBEINTERVIEW_OSS_ENDPOINT",
        "PROBEINTERVIEW_OSS_ACCESS_KEY_ID",
        "PROBEINTERVIEW_OSS_ACCESS_KEY_SECRET",
    )
    if any(not os.getenv(name) for name in required):
        pytest.skip("OSS smoke environment variables are not intentionally loaded")
    if os.getenv("PROBEINTERVIEW_OSS_BUCKET") != "probeinterview-test-kb-bucket":
        pytest.skip("OSS smoke requires the dedicated probeinterview test bucket")

    settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://unused:unused@localhost/unused",
        celery_broker_url="redis://localhost:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="oss-smoke",
        object_storage_adapter="oss",
        _env_file=None,
    )
    storage = OssObjectStorage.from_settings(settings)
    content = b"probeinterview OSS contract smoke"
    object_key = f"knowledge-sources/{uuid4()}.md"
    storage.put(
        object_key=object_key,
        content=content,
        content_type="text/markdown; charset=utf-8",
        checksum_sha256=sha256(content).hexdigest(),
    )
    storage.delete(object_key=object_key)
