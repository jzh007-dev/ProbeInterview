"""Knowledge source upload and owner-collection use cases."""

from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4
from zoneinfo import ZoneInfo

from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.knowledge.source.application.contracts import (
    KnowledgeSourceCollection,
    KnowledgeSourceRepository,
    KnowledgeSourceUpload,
    ObjectStorage,
    ReservationRequest,
)
from probeinterview.knowledge.source.application.errors import (
    ObjectStorageUnavailable,
    PublicUploadForbidden,
    UploadFinalizationFailed,
)
from probeinterview.knowledge.source.application.validation import (
    NORMALIZED_MEDIA_TYPE,
    validate_markdown,
    validate_scope,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


class KnowledgeSourceService:
    """Coordinate validation, database reservation, storage, and compensation."""

    def __init__(
        self,
        *,
        repository: KnowledgeSourceRepository,
        storage: ObjectStorage,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))

    def upload(
        self,
        *,
        actor: ActorContext,
        filename: str | None,
        content: bytes,
        scope_value: str | None,
        idempotency_key: str,
        original_filename: str | None = None,
    ) -> KnowledgeSourceUpload:
        scope = validate_scope(scope_value)
        filename_override_present = original_filename is not None
        selected_filename = original_filename if filename_override_present else filename
        safe_filename, content_sha256 = validate_markdown(
            selected_filename,
            content,
            filename_field="original_filename" if filename_override_present else "file",
        )
        if scope == "PUBLIC" and "knowledge.submit_public" not in actor.capabilities:
            raise PublicUploadForbidden
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 255:
            from probeinterview.knowledge.source.application.errors import (
                FieldError,
                InvalidUpload,
            )

            raise InvalidUpload(
                errors=(
                    FieldError(
                        field="Idempotency-Key",
                        message="A non-empty Idempotency-Key is required.",
                        code="invalid_idempotency_key",
                    ),
                )
            )

        now = self._clock().astimezone(UTC)
        quota_day = now.astimezone(SHANGHAI).date()
        source_id = uuid4()
        version_id = uuid4()
        object_key = f"knowledge-sources/{version_id}.md"
        request_digest = sha256(f"{scope}\0{safe_filename}\0{content_sha256}".encode()).hexdigest()
        reservation = self._repository.reserve(
            ReservationRequest(
                actor_id=actor.actor_id,
                scope=scope,
                original_filename=safe_filename,
                byte_size=len(content),
                content_sha256=content_sha256,
                idempotency_key=normalized_key,
                request_digest=request_digest,
                quota_day=quota_day,
                now=now,
                proposed_source_id=source_id,
                proposed_version_id=version_id,
                proposed_object_key=object_key,
            )
        )
        if reservation.stored_result is not None:
            return reservation.stored_result

        try:
            self._storage.put(
                object_key=reservation.object_key,
                content=content,
                content_type=NORMALIZED_MEDIA_TYPE,
                checksum_sha256=content_sha256,
            )
        except ObjectStorageUnavailable:
            self._repository.fail(actor.actor_id, reservation.source_id, "storage_unavailable")
            raise
        except Exception as error:
            self._repository.fail(actor.actor_id, reservation.source_id, "storage_unavailable")
            raise ObjectStorageUnavailable from error

        try:
            return self._repository.finalize(actor.actor_id, reservation.source_id, now)
        except Exception as error:
            with suppress(Exception):
                self._storage.delete(object_key=reservation.object_key)
            with suppress(Exception):
                self._repository.fail(
                    actor.actor_id,
                    reservation.source_id,
                    "finalization_failed",
                )
            raise UploadFinalizationFailed from error

    def list_for_actor(self, actor: ActorContext) -> KnowledgeSourceCollection:
        now = self._clock().astimezone(UTC)
        return self._repository.list_for_actor(
            actor.actor_id,
            now.astimezone(SHANGHAI).date(),
        )
