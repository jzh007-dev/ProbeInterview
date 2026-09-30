"""Bounded Markdown upload validation without parsing document structure."""

from hashlib import sha256
from pathlib import PurePath

from probeinterview.knowledge.source.application.contracts import KnowledgeScope
from probeinterview.knowledge.source.application.errors import (
    FieldError,
    InvalidUpload,
    UploadTooLarge,
)

MAX_MARKDOWN_BYTES = 500 * 1024
NORMALIZED_MEDIA_TYPE = "text/markdown; charset=utf-8"


def validate_scope(value: str | None) -> KnowledgeScope:
    """Validate the form scope before any authorization or mutation."""

    normalized = (value or "PRIVATE").upper()
    if normalized not in {"PRIVATE", "PUBLIC"}:
        raise InvalidUpload(
            errors=(
                FieldError(
                    field="scope",
                    message="Scope must be PRIVATE or PUBLIC.",
                    code="invalid_scope",
                ),
            )
        )
    return normalized  # type: ignore[return-value]


def validate_markdown(
    filename: str | None,
    content: bytes,
    *,
    filename_field: str = "file",
) -> tuple[str, str]:
    """Return a safe basename and SHA-256 for one valid Markdown payload."""

    safe_name = PurePath((filename or "").replace("\\", "/")).name
    if not safe_name or len(safe_name) > 255 or not safe_name.lower().endswith(".md"):
        raise InvalidUpload(
            errors=(
                FieldError(
                    field=filename_field,
                    message="Select a Markdown file whose name ends in .md.",
                    code="invalid_markdown_filename",
                ),
            )
        )
    if len(content) >= MAX_MARKDOWN_BYTES:
        raise UploadTooLarge(
            errors=(
                FieldError(
                    field="file",
                    message="The Markdown file must be smaller than 500 KiB.",
                    code="file_too_large",
                ),
            )
        )
    if not content:
        raise InvalidUpload(
            errors=(
                FieldError(
                    field="file",
                    message="The Markdown file must not be empty.",
                    code="empty_file",
                ),
            )
        )
    if b"\x00" in content:
        raise InvalidUpload(
            errors=(
                FieldError(
                    field="file",
                    message="The Markdown file must not contain NUL bytes.",
                    code="nul_byte",
                ),
            )
        )
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidUpload(
            errors=(
                FieldError(
                    field="file",
                    message="The Markdown file must be valid UTF-8.",
                    code="invalid_utf8",
                ),
            )
        ) from error
    return safe_name, sha256(content).hexdigest()
