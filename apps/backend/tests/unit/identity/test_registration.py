"""Registration service orchestration covers validation and compensation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from probeinterview.identity.access.application.exchange import ExchangeSnapshot
from probeinterview.identity.access.application.registration import (
    RegistrationFieldInvalid,
    RegistrationStorageUnavailable,
    RegistrationStoreCommand,
    RegistrationTokenInvalid,
    validate_avatar,
    validate_nickname,
)
from probeinterview.identity.access.application.tokens import token_digest
from probeinterview.platform.foundation.infrastructure.object_storage import FakeObjectStorage

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)

SNAPSHOT = ExchangeSnapshot(
    user_id=ACTOR_ID,
    nickname="新用户",
    avatar_object_key=None,
    default_target_profile=None,
    capabilities=frozenset(),
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"payload"


class FakeRegistrationStore:
    def __init__(self, user_id: UUID | None = None, error: Exception | None = None):
        self.user_id = user_id or uuid4()
        self.error = error
        self.commands: list[RegistrationStoreCommand] = []
        self.uploads: list[str | None] = []

    def register(self, command: RegistrationStoreCommand, upload_avatar) -> UUID:
        if self.error is not None:
            raise self.error
        # The real store persists only after the avatar upload succeeds.
        self.uploads.append(upload_avatar(self.user_id, uuid4()))
        self.commands.append(command)
        return self.user_id


class CommitFailureStore(FakeRegistrationStore):
    def register(self, command: RegistrationStoreCommand, upload_avatar) -> UUID:
        upload_avatar(uuid4(), uuid4())
        raise RuntimeError("commit failed after upload")


def make_service(store: FakeRegistrationStore, storage: FakeObjectStorage | None = None):
    from probeinterview.identity.access.application.registration import RegistrationService

    snapshots = FakeSnapshots({store.user_id: SNAPSHOT})
    sessions = FakeSessions()
    return (
        RegistrationService(
            registrations=store,
            snapshots=snapshots,
            sessions=sessions,
            storage=storage or FakeObjectStorage(),
            clock=lambda: NOW,
        ),
        snapshots,
        sessions,
    )


class FakeSnapshots:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.requested: list[UUID] = []

    def get_snapshot(self, user_id):
        self.requested.append(user_id)
        return self.snapshots.get(user_id)


class FakeSessions:
    def __init__(self):
        self.created = []

    def create(self, *, user_id, token_digest, expires_at):
        self.created.append((user_id, token_digest, expires_at))


class TestNicknameValidation:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  小明  ", "小明"),
            ("Bao", "Bao"),
            ("a" * 100, "a" * 100),
        ],
    )
    def test_valid_nicknames_are_trimmed(self, raw: str, expected: str) -> None:
        assert validate_nickname(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "a" * 101, "bad\x00name", "bad\nname", "bad\x1fname", "bad\x85name"],
    )
    def test_invalid_nicknames_raise_field_errors(self, raw: str) -> None:
        with pytest.raises(RegistrationFieldInvalid) as error:
            validate_nickname(raw)
        assert error.value.field == "nickname"
        assert error.value.code == "invalid_nickname"


class TestAvatarValidation:
    def test_valid_png_passes_with_extension(self) -> None:
        content, extension = validate_avatar(PNG_BYTES, "image/png")
        assert content == PNG_BYTES
        assert extension == ".png"

    def test_valid_jpeg_magic_passes(self) -> None:
        content, extension = validate_avatar(b"\xff\xd8\xff\xe0rest", "image/jpeg")
        assert extension == ".jpg"

    def test_valid_webp_magic_passes(self) -> None:
        content, extension = validate_avatar(b"RIFF\x00\x00\x00\x00WEBPal", "image/webp")
        assert extension == ".webp"

    @pytest.mark.parametrize(
        "content,media_type",
        [
            (PNG_BYTES, None),
            (PNG_BYTES, "image/gif"),
            (b"", "image/png"),
            (b"\x00\x00\x00\x00", "image/png"),
            (b"GIF89awhatever", "image/png"),
            (b"a" * (5 * 1024 * 1024 + 1), "image/png"),
        ],
    )
    def test_invalid_avatars_raise_field_errors(self, content: bytes, media_type) -> None:
        with pytest.raises(RegistrationFieldInvalid) as error:
            validate_avatar(content, media_type)
        assert error.value.field == "file"
        assert error.value.code == "invalid_avatar"


def test_default_avatar_registration_invokes_no_upload() -> None:
    store = FakeRegistrationStore()
    service, snapshots, sessions = make_service(store)

    result = service.register(registration_token="one-time-token", nickname="  新用户  ")

    assert result.current_user is SNAPSHOT
    assert result.token_type == "Bearer"
    command = store.commands[0]
    assert command.nickname == "新用户"
    assert command.registration_digest == token_digest("one-time-token")
    assert command.session_digest == token_digest(result.access_token)
    assert command.session_expires_at > command.now
    assert store.uploads == [None]
    assert snapshots.requested == [store.user_id]
    assert sessions.created == []


def test_custom_avatar_registration_stores_object_key() -> None:
    store = FakeRegistrationStore()
    storage = FakeObjectStorage()
    service, _, _ = make_service(store, storage)

    result = service.register(
        registration_token="one-time-token",
        nickname="新用户",
        avatar_content=PNG_BYTES,
        avatar_media_type="image/png",
    )

    assert store.uploads[0] is not None
    object_key = str(store.uploads[0])
    assert object_key.startswith(f"avatars/{store.user_id}/")
    assert object_key.endswith(".png")
    assert storage.objects[object_key].content == PNG_BYTES
    assert result.current_user.avatar_object_key == SNAPSHOT.avatar_object_key


def test_storage_failure_rolls_back_without_user_state() -> None:
    store = FakeRegistrationStore()
    service, _, _ = make_service(store, FakeObjectStorage(fail_put=True))

    with pytest.raises(RegistrationStorageUnavailable):
        service.register(
            registration_token="one-time-token",
            nickname="新用户",
            avatar_content=PNG_BYTES,
            avatar_media_type="image/png",
        )

    assert store.commands == []


def test_commit_failure_deletes_the_unreferenced_object() -> None:
    storage = FakeObjectStorage()
    service, _, _ = make_service(CommitFailureStore(), storage)
    uploaded_keys: list[str] = []
    original_put = storage.put

    def recording_put(*, object_key, content, content_type, checksum_sha256) -> None:
        original_put(
            object_key=object_key,
            content=content,
            content_type=content_type,
            checksum_sha256=checksum_sha256,
        )
        uploaded_keys.append(object_key)

    storage.put = recording_put  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="commit failed"):
        service.register(
            registration_token="one-time-token",
            nickname="新用户",
            avatar_content=PNG_BYTES,
            avatar_media_type="image/png",
        )

    assert len(uploaded_keys) == 1
    assert uploaded_keys[0] not in storage.objects
    assert [call.operation for call in storage.calls] == ["put", "delete"]


def test_invalid_credential_propagates_without_persistence() -> None:
    store = FakeRegistrationStore(error=RegistrationTokenInvalid())
    service, _, _ = make_service(store)

    with pytest.raises(RegistrationTokenInvalid):
        service.register(registration_token="bad", nickname="新用户")

    assert store.commands == []
