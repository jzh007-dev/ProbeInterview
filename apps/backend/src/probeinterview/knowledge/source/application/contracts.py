"""Provider-neutral contracts and application resources."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID

KnowledgeScope = Literal["PRIVATE", "PUBLIC"]


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    """Safe quota values returned to the current owner."""

    timezone: str
    daily_limit: int
    daily_used: int
    effective_source_limit: int
    effective_source_count: int


@dataclass(frozen=True, slots=True)
class KnowledgeSourceItem:
    """Display-safe owner resource."""

    id: UUID
    original_filename: str
    scope: KnowledgeScope
    processing_status: Literal["PENDING_EXTRACTION"]
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeSourceUpload:
    """Accepted upload plus current quota context."""

    source: KnowledgeSourceItem
    quota: QuotaSnapshot


@dataclass(frozen=True, slots=True)
class KnowledgeSourceCollection:
    """Owner-only collection plus current quota context."""

    quota: QuotaSnapshot
    items: tuple[KnowledgeSourceItem, ...]


@dataclass(frozen=True, slots=True)
class ReservationRequest:
    """Validated values required for database admission."""

    actor_id: UUID
    scope: KnowledgeScope
    original_filename: str
    byte_size: int
    content_sha256: str
    idempotency_key: str
    request_digest: str
    quota_day: date
    now: datetime
    proposed_source_id: UUID
    proposed_version_id: UUID
    proposed_object_key: str


@dataclass(frozen=True, slots=True)
class UploadReservation:
    """Reservation to write, or an already stored no-op result."""

    source_id: UUID
    version_id: UUID
    object_key: str
    stored_result: KnowledgeSourceUpload | None = None


class KnowledgeSourceRepository(Protocol):
    """Persistence operations that preserve admission invariants."""

    def reserve(self, request: ReservationRequest) -> UploadReservation: ...

    def finalize(self, actor_id: UUID, source_id: UUID, now: datetime) -> KnowledgeSourceUpload: ...

    def fail(self, actor_id: UUID, source_id: UUID, failure_code: str) -> None: ...

    def list_for_actor(
        self,
        actor_id: UUID,
        quota_day: date,
    ) -> KnowledgeSourceCollection: ...


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
