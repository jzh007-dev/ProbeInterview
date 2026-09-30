"""First-registration orchestration with atomic identity creation."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from probeinterview.identity.access.application.exchange import (
    AuthenticatedExchange,
    AuthSessionStore,
    ExchangeSnapshotReader,
)
from probeinterview.identity.access.application.tokens import (
    SESSION_TTL,
    new_session_token,
    token_digest,
)
from probeinterview.platform.foundation.application.object_storage import (
    ObjectStorage,
    ObjectStorageUnavailable,
)

NICKNAME_MAX_LENGTH = 100
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class RegistrationTokenInvalid(Exception):
    """The registration credential is unknown, expired, or irreconcilable."""


class RegistrationStorageUnavailable(Exception):
    """Private object storage rejected the avatar write."""


class RegistrationFieldInvalid(Exception):
    """One registration field violated its display-safe validation rules."""

    def __init__(self, *, field: str, message: str, code: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


def validate_nickname(nickname: str) -> str:
    """Return the trimmed display-safe nickname or raise a field error."""

    normalized = nickname.strip()
    if not normalized:
        raise RegistrationFieldInvalid(
            field="nickname",
            message="A non-empty nickname is required.",
            code="invalid_nickname",
        )
    if len(normalized) > NICKNAME_MAX_LENGTH:
        raise RegistrationFieldInvalid(
            field="nickname",
            message=f"The nickname must contain at most {NICKNAME_MAX_LENGTH} characters.",
            code="invalid_nickname",
        )
    if any(_is_control(char) for char in normalized):
        raise RegistrationFieldInvalid(
            field="nickname",
            message="The nickname must not contain control characters.",
            code="invalid_nickname",
        )
    return normalized


def validate_avatar(content: bytes, declared_media_type: str | None) -> tuple[bytes, str]:
    """Return validated avatar bytes and extension or raise a field error."""

    if declared_media_type not in AVATAR_EXTENSIONS:
        raise RegistrationFieldInvalid(
            field="file",
            message="The avatar must be a JPEG, PNG, or WebP image.",
            code="invalid_avatar",
        )
    if not content:
        raise RegistrationFieldInvalid(
            field="file",
            message="The avatar file must not be empty.",
            code="invalid_avatar",
        )
    if len(content) > AVATAR_MAX_BYTES:
        raise RegistrationFieldInvalid(
            field="file",
            message="The avatar file must not exceed 5 MiB.",
            code="invalid_avatar",
        )
    if not _magic_bytes_match(content, declared_media_type):
        raise RegistrationFieldInvalid(
            field="file",
            message="The avatar file content does not match its declared type.",
            code="invalid_avatar",
        )
    return content, AVATAR_EXTENSIONS[declared_media_type]


def _is_control(char: str) -> bool:
    return "\x00" <= char <= "\x1f" or "\x7f" <= char <= "\x9f"


def _magic_bytes_match(content: bytes, declared_media_type: str) -> bool:
    if declared_media_type == "image/jpeg":
        return content[:3] == b"\xff\xd8\xff"
    if declared_media_type == "image/png":
        return content[:8] == b"\x89PNG\r\n\x1a\n"
    return content[:4] == b"RIFF" and content[8:12] == b"WEBP"


@dataclass(frozen=True, slots=True)
class RegistrationStoreCommand:
    """Everything the store needs to create one identity atomically."""

    registration_digest: str
    session_digest: str
    session_expires_at: datetime
    nickname: str
    now: datetime


class RegistrationStore(Protocol):
    """Serialize, converge, and persist one first registration."""

    def register(
        self,
        command: RegistrationStoreCommand,
        upload_avatar: Callable[[UUID, UUID], str | None],
    ) -> UUID:
        """Return the winning user id after commit.

        ``upload_avatar`` is invoked for the lock winner only and must return
        the stored object key, or None for the default-avatar path. Storage
        failures roll the transaction back; commit failures propagate after
        the upload so the caller can compensate.
        """
        ...


class RegistrationService:
    """Create users, WeChat bindings, avatars, and sessions as one operation."""

    def __init__(
        self,
        *,
        registrations: RegistrationStore,
        snapshots: ExchangeSnapshotReader,
        sessions: AuthSessionStore,
        storage: ObjectStorage,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registrations = registrations
        self._snapshots = snapshots
        self._sessions = sessions
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))

    def register(
        self,
        *,
        registration_token: str,
        nickname: str,
        avatar_content: bytes | None = None,
        avatar_media_type: str | None = None,
    ) -> AuthenticatedExchange:
        """Validate, converge, and persist one registration; return the session."""

        safe_nickname = validate_nickname(nickname)
        validated_avatar: tuple[bytes, str] | None = None
        if avatar_content is not None:
            validated_avatar = validate_avatar(avatar_content, avatar_media_type)

        access_token = new_session_token()
        now = self._clock().astimezone(UTC)
        written_keys: list[str] = []

        def upload_avatar(user_id: UUID, avatar_id: UUID) -> str | None:
            if validated_avatar is None:
                return None
            content, extension = validated_avatar
            object_key = f"avatars/{user_id}/{avatar_id}{extension}"
            self._storage.put(
                object_key=object_key,
                content=content,
                content_type=avatar_media_type or "application/octet-stream",
                checksum_sha256=hashlib.sha256(content).hexdigest(),
            )
            written_keys.append(object_key)
            return object_key

        try:
            user_id = self._registrations.register(
                RegistrationStoreCommand(
                    registration_digest=token_digest(registration_token),
                    session_digest=token_digest(access_token),
                    session_expires_at=now + SESSION_TTL,
                    nickname=safe_nickname,
                    now=now,
                ),
                upload_avatar,
            )
        except ObjectStorageUnavailable:
            raise RegistrationStorageUnavailable from None
        except Exception:
            for object_key in written_keys:
                self._storage.delete(object_key=object_key)
            raise

        snapshot = self._snapshots.get_snapshot(user_id)
        if snapshot is None:
            raise RegistrationTokenInvalid
        return AuthenticatedExchange(
            access_token=access_token,
            token_type="Bearer",
            expires_at=now + SESSION_TTL,
            current_user=snapshot,
        )
