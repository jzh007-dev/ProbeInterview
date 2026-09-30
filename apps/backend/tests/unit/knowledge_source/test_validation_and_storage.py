"""Fast coverage for bounded validation and provider-neutral storage."""

from hashlib import sha256

import pytest

from probeinterview.knowledge.source.application.errors import (
    InvalidUpload,
    UploadTooLarge,
)
from probeinterview.knowledge.source.application.validation import (
    MAX_MARKDOWN_BYTES,
    NORMALIZED_MEDIA_TYPE,
    validate_markdown,
    validate_scope,
)
from probeinterview.platform.foundation.application.object_storage import (
    ObjectStorageUnavailable,
)
from probeinterview.platform.foundation.infrastructure.object_storage import (
    FakeObjectStorage,
    OssObjectStorage,
)

OBJECT_KEY = "knowledge-sources/44d9b815-1c88-4345-aa45-969db30d4d5a.md"


@pytest.mark.parametrize("filename", ["notes.md", "NOTES.MD", r"C:\fakepath\notes.md"])
def test_validation_accepts_markdown_without_parsing(filename: str) -> None:
    safe_name, digest = validate_markdown(filename, b"# heading\n<custom>ok</custom>")

    assert safe_name == "notes.md" or safe_name == "NOTES.MD"
    assert digest == sha256(b"# heading\n<custom>ok</custom>").hexdigest()


@pytest.mark.parametrize(
    ("filename", "content", "error_type", "code"),
    [
        ("notes.txt", b"valid text", InvalidUpload, "invalid_markdown_filename"),
        ("notes.md", b"", InvalidUpload, "empty_file"),
        ("notes.md", b"\xff", InvalidUpload, "invalid_utf8"),
        ("notes.md", b"a\x00b", InvalidUpload, "nul_byte"),
        ("notes.md", b"a" * MAX_MARKDOWN_BYTES, UploadTooLarge, "file_too_large"),
    ],
)
def test_validation_rejects_invalid_input_without_side_effects(
    filename: str,
    content: bytes,
    error_type: type[InvalidUpload],
    code: str,
) -> None:
    with pytest.raises(error_type) as error:
        validate_markdown(filename, content)

    assert error.value.errors[0].code == code


def test_scope_defaults_private_and_rejects_unknown_values() -> None:
    assert validate_scope(None) == "PRIVATE"
    assert validate_scope("public") == "PUBLIC"
    with pytest.raises(InvalidUpload) as error:
        validate_scope("friends")
    assert error.value.errors[0].code == "invalid_scope"


def test_fake_and_oss_adapters_share_metadata_and_delete_contract() -> None:
    content = b"# private source"
    checksum = sha256(content).hexdigest()
    fake = FakeObjectStorage()
    fake.put(
        object_key=OBJECT_KEY,
        content=content,
        content_type=NORMALIZED_MEDIA_TYPE,
        checksum_sha256=checksum,
    )
    assert fake.objects[OBJECT_KEY].checksum_sha256 == checksum
    assert fake.calls[0].byte_size == len(content)
    fake.delete(object_key=OBJECT_KEY)
    assert fake.objects == {}

    bucket = RecordingBucket()
    oss = OssObjectStorage(bucket)
    oss.put(
        object_key=OBJECT_KEY,
        content=content,
        content_type=NORMALIZED_MEDIA_TYPE,
        checksum_sha256=checksum,
    )
    assert bucket.puts == [
        (
            OBJECT_KEY,
            content,
            {
                "Content-Type": NORMALIZED_MEDIA_TYPE,
                "x-oss-meta-sha256": checksum,
            },
        )
    ]
    oss.delete(object_key=OBJECT_KEY)
    assert bucket.deletes == [OBJECT_KEY]


def test_storage_errors_are_safely_mapped() -> None:
    storage = OssObjectStorage(FailingBucket())
    with pytest.raises(ObjectStorageUnavailable) as put_error:
        storage.put(
            object_key="safe-key",
            content=b"private",
            content_type=NORMALIZED_MEDIA_TYPE,
            checksum_sha256=sha256(b"private").hexdigest(),
        )
    with pytest.raises(ObjectStorageUnavailable) as delete_error:
        storage.delete(object_key="safe-key")

    for error in (put_error.value, delete_error.value):
        assert error.__cause__ is None
        assert error.__suppress_context__ is True


class RecordingBucket:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, dict[str, str]]] = []
        self.deletes: list[str] = []

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


class FailingBucket:
    def put_object(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private provider failure")

    def delete_object(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private provider failure")
