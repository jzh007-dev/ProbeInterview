"""Deterministic fake and Alibaba OSS private-object adapters."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from urllib.parse import quote, urlencode

from probeinterview.platform.foundation.application.object_storage import (
    DEFAULT_SIGNED_GET_LIFETIME,
    ObjectStorageUnavailable,
    SignedObjectUrl,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Fake-only stored value used by contract tests."""

    content: bytes
    content_type: str
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class StorageCall:
    """Safe fake call metadata that excludes private source text."""

    operation: str
    object_key: str
    byte_size: int | None = None
    content_type: str | None = None
    checksum_sha256: str | None = None


class FakeObjectStorage:
    """Thread-safe deterministic storage for tests and local development."""

    def __init__(
        self,
        *,
        fail_put: bool = False,
        fail_delete: bool = False,
        fail_sign: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.calls: list[StorageCall] = []
        self.fail_put = fail_put
        self.fail_delete = fail_delete
        self.fail_sign = fail_sign
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = Lock()

    def put(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str,
        checksum_sha256: str,
    ) -> None:
        with self._lock:
            self.calls.append(
                StorageCall(
                    operation="put",
                    object_key=object_key,
                    byte_size=len(content),
                    content_type=content_type,
                    checksum_sha256=checksum_sha256,
                )
            )
            if self.fail_put:
                raise ObjectStorageUnavailable
            self.objects[object_key] = StoredObject(
                content=content,
                content_type=content_type,
                checksum_sha256=checksum_sha256,
            )

    def delete(self, *, object_key: str) -> None:
        with self._lock:
            self.calls.append(StorageCall(operation="delete", object_key=object_key))
            if self.fail_delete:
                raise ObjectStorageUnavailable
            self.objects.pop(object_key, None)

    def sign_get_url(
        self,
        *,
        object_key: str,
        expires_in: timedelta = DEFAULT_SIGNED_GET_LIFETIME,
    ) -> SignedObjectUrl:
        with self._lock:
            self.calls.append(StorageCall(operation="sign_get_url", object_key=object_key))
            if self.fail_sign:
                raise ObjectStorageUnavailable
        expires_at = self._clock().astimezone(UTC) + expires_in
        query = urlencode({"expires_at": expires_at.isoformat()})
        return SignedObjectUrl(
            url=f"https://object-storage.invalid/{quote(object_key)}?{query}",
            expires_at=expires_at,
        )


class OssObjectStorage:
    """Private Alibaba OSS adapter with safe exception mapping."""

    def __init__(
        self,
        bucket: Any,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bucket = bucket
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_settings(cls, settings: Settings) -> "OssObjectStorage":
        try:
            import oss2

            if (
                settings.oss_endpoint is None
                or settings.oss_bucket is None
                or settings.oss_access_key_id is None
                or settings.oss_access_key_secret is None
            ):
                raise ValueError("OSS adapter requires endpoint, bucket, and credentials")
            auth = oss2.Auth(
                settings.oss_access_key_id,
                settings.oss_access_key_secret.get_secret_value(),
            )
            return cls(oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket))
        except ObjectStorageUnavailable:
            raise
        except Exception as error:
            raise ValueError("OSS adapter configuration is invalid") from error

    def put(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str,
        checksum_sha256: str,
    ) -> None:
        try:
            self._bucket.put_object(
                object_key,
                content,
                headers={
                    "Content-Type": content_type,
                    "x-oss-meta-sha256": checksum_sha256,
                },
            )
        except Exception:
            raise ObjectStorageUnavailable from None

    def delete(self, *, object_key: str) -> None:
        try:
            self._bucket.delete_object(object_key)
        except Exception:
            raise ObjectStorageUnavailable from None

    def sign_get_url(
        self,
        *,
        object_key: str,
        expires_in: timedelta = DEFAULT_SIGNED_GET_LIFETIME,
    ) -> SignedObjectUrl:
        expires_seconds = int(expires_in.total_seconds())
        try:
            url = self._bucket.sign_url("GET", object_key, expires_seconds)
        except Exception:
            raise ObjectStorageUnavailable from None
        return SignedObjectUrl(
            url=url,
            expires_at=self._clock().astimezone(UTC) + expires_in,
        )


def build_object_storage(settings: Settings) -> FakeObjectStorage | OssObjectStorage:
    """Select exactly the configured adapter without production fallback."""

    if settings.object_storage_adapter == "fake":
        if settings.environment == "production":
            raise ValueError("production forbids fake object storage")
        return FakeObjectStorage()
    return OssObjectStorage.from_settings(settings)
