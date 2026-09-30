"""Provider-neutral private object-storage boundary."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

DEFAULT_SIGNED_GET_LIFETIME = timedelta(minutes=10)


class ObjectStorageUnavailable(Exception):
    """Safe platform failure raised when private object storage is unavailable."""

    def __init__(self) -> None:
        super().__init__("object storage unavailable")


@dataclass(frozen=True, slots=True)
class SignedObjectUrl:
    """Short-lived private object display URL."""

    url: str
    expires_at: datetime


class ObjectStorage(Protocol):
    """Provider-neutral private object storage."""

    def put(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str,
        checksum_sha256: str,
    ) -> None: ...

    def delete(self, *, object_key: str) -> None: ...

    def sign_get_url(
        self,
        *,
        object_key: str,
        expires_in: timedelta = DEFAULT_SIGNED_GET_LIFETIME,
    ) -> SignedObjectUrl: ...
