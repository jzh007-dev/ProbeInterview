from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from probeinterview.platform.foundation.application.object_storage import (
    ObjectStorageUnavailable,
)
from probeinterview.platform.foundation.infrastructure.object_storage import (
    FakeObjectStorage,
    OssObjectStorage,
)

OBJECT_KEY = "avatars/user/avatar.png"
NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


def test_fake_storage_delete_is_idempotent_and_signed_url_is_deterministic() -> None:
    content = b"private"
    storage = FakeObjectStorage(clock=lambda: NOW)
    storage.put(
        object_key=OBJECT_KEY,
        content=content,
        content_type="image/png",
        checksum_sha256=sha256(content).hexdigest(),
    )

    storage.delete(object_key=OBJECT_KEY)
    storage.delete(object_key=OBJECT_KEY)
    signed = storage.sign_get_url(object_key=OBJECT_KEY)

    assert storage.objects == {}
    assert [call.operation for call in storage.calls] == [
        "put",
        "delete",
        "delete",
        "sign_get_url",
    ]
    assert signed.url == (
        "https://object-storage.invalid/avatars/user/avatar.png"
        "?expires_at=2026-09-30T08%3A10%3A00%2B00%3A00"
    )
    assert signed.expires_at == NOW + timedelta(minutes=10)


def test_oss_storage_supports_private_put_idempotent_delete_and_signed_get() -> None:
    content = b"private"
    bucket = RecordingBucket()
    storage = OssObjectStorage(bucket, clock=lambda: NOW)

    storage.put(
        object_key=OBJECT_KEY,
        content=content,
        content_type="image/png",
        checksum_sha256=sha256(content).hexdigest(),
    )
    storage.delete(object_key=OBJECT_KEY)
    storage.delete(object_key=OBJECT_KEY)
    signed = storage.sign_get_url(object_key=OBJECT_KEY)

    assert len(bucket.puts) == 1
    assert bucket.deletes == [OBJECT_KEY, OBJECT_KEY]
    assert bucket.signs == [("GET", OBJECT_KEY, 600)]
    assert signed.url == "https://oss.example.invalid/signed-avatar"
    assert signed.expires_at == NOW + timedelta(minutes=10)


@pytest.mark.parametrize("operation", ["put", "delete", "sign_get_url"])
def test_oss_provider_failures_map_without_raw_exception_details(operation: str) -> None:
    storage = OssObjectStorage(FailingBucket(), clock=lambda: NOW)

    with pytest.raises(ObjectStorageUnavailable) as error:
        if operation == "put":
            storage.put(
                object_key=OBJECT_KEY,
                content=b"private",
                content_type="image/png",
                checksum_sha256=sha256(b"private").hexdigest(),
            )
        elif operation == "delete":
            storage.delete(object_key=OBJECT_KEY)
        else:
            storage.sign_get_url(object_key=OBJECT_KEY)

    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert "raw provider failure" not in str(error.value)


class RecordingBucket:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, dict[str, str]]] = []
        self.deletes: list[str] = []
        self.signs: list[tuple[str, str, int]] = []

    def put_object(
        self,
        object_key: str,
        content: bytes,
        *,
        headers: dict[str, str],
    ) -> None:
        self.puts.append((object_key, content, headers))

    def delete_object(self, object_key: str) -> None:
        self.deletes.append(object_key)

    def sign_url(self, method: str, object_key: str, expires: int) -> str:
        self.signs.append((method, object_key, expires))
        return "https://oss.example.invalid/signed-avatar"


class FailingBucket:
    def put_object(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("raw provider failure with credentials")

    def delete_object(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("raw provider failure with credentials")

    def sign_url(self, *_args: object, **_kwargs: object) -> str:
        raise RuntimeError("raw provider failure with credentials")
