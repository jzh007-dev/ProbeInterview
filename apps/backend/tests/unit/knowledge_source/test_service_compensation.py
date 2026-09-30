"""Application orchestration covers authorization and compensation boundaries."""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.knowledge.source.application.contracts import (
    KnowledgeSourceCollection,
    KnowledgeSourceItem,
    KnowledgeSourceUpload,
    QuotaSnapshot,
    ReservationRequest,
    UploadReservation,
)
from probeinterview.knowledge.source.application.errors import (
    PublicUploadForbidden,
    UploadFinalizationFailed,
)
from probeinterview.knowledge.source.application.service import KnowledgeSourceService
from probeinterview.knowledge.source.infrastructure.storage import FakeObjectStorage

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
NOW = datetime(2026, 9, 30, 5, 0, tzinfo=UTC)


def test_public_authorization_precedes_database_and_storage_mutation() -> None:
    repository = RecordingRepository()
    storage = FakeObjectStorage()
    service = make_service(repository, storage)

    with pytest.raises(PublicUploadForbidden):
        service.upload(
            actor=ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()),
            filename="public.md",
            content=b"# public",
            scope_value="PUBLIC",
            idempotency_key="public-1",
        )

    assert repository.reservations == []
    assert storage.calls == []


def test_finalization_failure_deletes_object_and_marks_reservation_failed() -> None:
    repository = RecordingRepository(fail_finalization=True)
    storage = FakeObjectStorage()
    service = make_service(repository, storage)

    with pytest.raises(UploadFinalizationFailed):
        service.upload(
            actor=ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()),
            filename="private.md",
            content=b"# private",
            scope_value=None,
            idempotency_key="private-1",
        )

    assert [call.operation for call in storage.calls] == ["put", "delete"]
    assert storage.objects == {}
    assert repository.failures == [("finalization_failed",)]


def test_upload_uses_one_unique_version_key_below_the_knowledge_sources_prefix() -> None:
    repository = RecordingRepository()
    storage = FakeObjectStorage()
    service = make_service(repository, storage)

    service.upload(
        actor=ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()),
        filename="private.md",
        content=b"# private",
        scope_value=None,
        idempotency_key="private-flat-key",
    )

    reservation = repository.reservations[0]
    assert reservation.proposed_object_key == (
        f"knowledge-sources/{reservation.proposed_version_id}.md"
    )


def make_service(
    repository: "RecordingRepository",
    storage: FakeObjectStorage,
) -> KnowledgeSourceService:
    return KnowledgeSourceService(
        repository=repository,
        storage=storage,
        clock=lambda: NOW,
    )


class RecordingRepository:
    def __init__(self, *, fail_finalization: bool = False) -> None:
        self.fail_finalization = fail_finalization
        self.reservations: list[ReservationRequest] = []
        self.failures: list[tuple[str]] = []

    def reserve(self, request: ReservationRequest) -> UploadReservation:
        self.reservations.append(request)
        return UploadReservation(
            source_id=request.proposed_source_id,
            version_id=request.proposed_version_id,
            object_key=request.proposed_object_key,
        )

    def finalize(
        self,
        actor_id: UUID,
        source_id: UUID,
        now: datetime,
    ) -> KnowledgeSourceUpload:
        if self.fail_finalization:
            raise RuntimeError("database failed")
        return KnowledgeSourceUpload(
            source=KnowledgeSourceItem(
                id=source_id,
                original_filename="private.md",
                scope="PRIVATE",
                processing_status="PENDING_EXTRACTION",
                uploaded_at=now,
            ),
            quota=QuotaSnapshot(
                timezone="Asia/Shanghai",
                daily_limit=2,
                daily_used=1,
                effective_source_limit=100,
                effective_source_count=1,
            ),
        )

    def fail(self, actor_id: UUID, source_id: UUID, failure_code: str) -> None:
        self.failures.append((failure_code,))

    def list_for_actor(
        self,
        actor_id: UUID,
        quota_day: date,
    ) -> KnowledgeSourceCollection:
        raise AssertionError("not used")
