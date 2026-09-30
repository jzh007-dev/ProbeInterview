"""PostgreSQL repository preserving owner, quota, and idempotency invariants."""

from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from probeinterview.knowledge.source.application.contracts import (
    KnowledgeScope,
    KnowledgeSourceCollection,
    KnowledgeSourceItem,
    KnowledgeSourceUpload,
    QuotaSnapshot,
    ReservationRequest,
    UploadReservation,
)
from probeinterview.knowledge.source.application.errors import (
    DailyUploadLimitReached,
    EffectiveSourceLimitReached,
    IdempotencyConflict,
    UploadInProgress,
    UploadPolicyUnavailable,
)
from probeinterview.knowledge.source.infrastructure.models import (
    KnowledgeSourceModel,
    KnowledgeSourceVersionModel,
    KnowledgeUploadPolicyModel,
)


class SqlAlchemyKnowledgeSourceRepository:
    """Use the actor policy row as the cross-process admission lock."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def reserve(self, request: ReservationRequest) -> UploadReservation:
        with self._session_factory.begin() as session:
            policy = session.scalar(
                select(KnowledgeUploadPolicyModel)
                .where(KnowledgeUploadPolicyModel.user_id == request.actor_id)
                .with_for_update()
            )
            if policy is None:
                raise UploadPolicyUnavailable

            bound = session.scalar(
                select(KnowledgeSourceModel).where(
                    KnowledgeSourceModel.owner_user_id == request.actor_id,
                    KnowledgeSourceModel.idempotency_key == request.idempotency_key,
                )
            )
            if bound is not None:
                if bound.request_digest != request.request_digest:
                    raise IdempotencyConflict
                if bound.ingestion_status == "STORED":
                    return UploadReservation(
                        source_id=bound.id,
                        version_id=cast(UUID, bound.current_version_id),
                        object_key=self._version_for_source(session, bound.id).object_key,
                        stored_result=self._upload_result(
                            session,
                            request.actor_id,
                            bound,
                            policy,
                            request.quota_day,
                        ),
                    )
                version = self._version_for_source(session, bound.id)
                if bound.ingestion_status == "FAILED":
                    bound.ingestion_status = "UPLOADING"
                    bound.failure_code = None
                    bound.quota_day = request.quota_day
                    version.storage_status = "UPLOADING"
                    version.processing_status = None
                    version.stored_at = None
                return UploadReservation(
                    source_id=bound.id,
                    version_id=version.id,
                    object_key=version.object_key,
                )

            duplicate = session.scalar(
                select(KnowledgeSourceModel).where(
                    KnowledgeSourceModel.owner_user_id == request.actor_id,
                    KnowledgeSourceModel.scope == request.scope,
                    KnowledgeSourceModel.content_sha256 == request.content_sha256,
                    KnowledgeSourceModel.ingestion_status.in_(("UPLOADING", "STORED")),
                )
            )
            if duplicate is not None:
                if duplicate.ingestion_status == "UPLOADING":
                    raise UploadInProgress
                return UploadReservation(
                    source_id=duplicate.id,
                    version_id=cast(UUID, duplicate.current_version_id),
                    object_key=self._version_for_source(session, duplicate.id).object_key,
                    stored_result=self._upload_result(
                        session,
                        request.actor_id,
                        duplicate,
                        policy,
                        request.quota_day,
                    ),
                )

            quota = self._quota(session, request.actor_id, request.quota_day, policy)
            daily_reserved = self._count(
                session,
                request.actor_id,
                statuses=("UPLOADING", "STORED"),
                quota_day=request.quota_day,
            )
            effective_reserved = self._count(
                session,
                request.actor_id,
                statuses=("UPLOADING", "STORED"),
            )
            if daily_reserved >= policy.daily_success_limit:
                raise DailyUploadLimitReached(quota=quota)
            if effective_reserved >= policy.effective_source_limit:
                raise EffectiveSourceLimitReached(quota=quota)

            source = KnowledgeSourceModel(
                id=request.proposed_source_id,
                owner_user_id=request.actor_id,
                creator_user_id=request.actor_id,
                scope=request.scope,
                ingestion_status="UPLOADING",
                content_sha256=request.content_sha256,
                quota_day=request.quota_day,
                idempotency_key=request.idempotency_key,
                request_digest=request.request_digest,
                current_version_id=None,
                created_at=request.now,
                stored_at=None,
                updated_at=request.now,
                failure_code=None,
            )
            version = KnowledgeSourceVersionModel(
                id=request.proposed_version_id,
                source_id=request.proposed_source_id,
                version_number=1,
                original_filename=request.original_filename,
                media_type="text/markdown; charset=utf-8",
                byte_size=request.byte_size,
                content_sha256=request.content_sha256,
                object_key=request.proposed_object_key,
                storage_status="UPLOADING",
                processing_status=None,
                created_at=request.now,
                stored_at=None,
                updated_at=request.now,
            )
            session.add_all((source, version))
            return UploadReservation(
                source_id=source.id,
                version_id=version.id,
                object_key=version.object_key,
            )

    def finalize(
        self,
        actor_id: UUID,
        source_id: UUID,
        now: datetime,
    ) -> KnowledgeSourceUpload:
        with self._session_factory.begin() as session:
            policy = session.scalar(
                select(KnowledgeUploadPolicyModel)
                .where(KnowledgeUploadPolicyModel.user_id == actor_id)
                .with_for_update()
            )
            if policy is None:
                raise UploadPolicyUnavailable
            source = session.scalar(
                select(KnowledgeSourceModel)
                .where(
                    KnowledgeSourceModel.id == source_id,
                    KnowledgeSourceModel.owner_user_id == actor_id,
                )
                .with_for_update()
            )
            if source is None:
                raise UploadPolicyUnavailable
            version = self._version_for_source(session, source.id)
            source.ingestion_status = "STORED"
            source.current_version_id = version.id
            source.stored_at = now
            source.updated_at = now
            source.failure_code = None
            version.storage_status = "STORED"
            version.processing_status = "PENDING_EXTRACTION"
            version.stored_at = now
            version.updated_at = now
            session.flush()
            return self._upload_result(
                session,
                actor_id,
                source,
                policy,
                source.quota_day,
            )

    def fail(self, actor_id: UUID, source_id: UUID, failure_code: str) -> None:
        with self._session_factory.begin() as session:
            source = session.scalar(
                select(KnowledgeSourceModel)
                .where(
                    KnowledgeSourceModel.id == source_id,
                    KnowledgeSourceModel.owner_user_id == actor_id,
                )
                .with_for_update()
            )
            if source is None or source.ingestion_status == "STORED":
                return
            source.ingestion_status = "FAILED"
            source.failure_code = failure_code
            version = self._version_for_source(session, source.id)
            version.storage_status = "FAILED"
            version.processing_status = None

    def list_for_actor(
        self,
        actor_id: UUID,
        quota_day: date,
    ) -> KnowledgeSourceCollection:
        with self._session_factory() as session:
            policy = session.scalar(
                select(KnowledgeUploadPolicyModel).where(
                    KnowledgeUploadPolicyModel.user_id == actor_id
                )
            )
            if policy is None:
                raise UploadPolicyUnavailable
            sources = session.scalars(
                select(KnowledgeSourceModel)
                .where(
                    KnowledgeSourceModel.owner_user_id == actor_id,
                    KnowledgeSourceModel.ingestion_status == "STORED",
                )
                .order_by(
                    KnowledgeSourceModel.stored_at.desc(),
                    KnowledgeSourceModel.id.desc(),
                )
            ).all()
            items = tuple(self._item(session, source) for source in sources)
            quota = self._quota(session, actor_id, quota_day, policy)
        return KnowledgeSourceCollection(quota=quota, items=items)

    def _upload_result(
        self,
        session: Session,
        actor_id: UUID,
        source: KnowledgeSourceModel,
        policy: KnowledgeUploadPolicyModel,
        quota_day: date,
    ) -> KnowledgeSourceUpload:
        session.flush()
        return KnowledgeSourceUpload(
            source=self._item(session, source),
            quota=self._quota(session, actor_id, quota_day, policy),
        )

    def _item(
        self,
        session: Session,
        source: KnowledgeSourceModel,
    ) -> KnowledgeSourceItem:
        version = self._version_for_source(session, source.id)
        if source.stored_at is None or version.processing_status != "PENDING_EXTRACTION":
            raise UploadPolicyUnavailable
        return KnowledgeSourceItem(
            id=source.id,
            original_filename=version.original_filename,
            scope=cast(KnowledgeScope, source.scope),
            processing_status="PENDING_EXTRACTION",
            uploaded_at=source.stored_at,
        )

    @staticmethod
    def _version_for_source(
        session: Session,
        source_id: UUID,
    ) -> KnowledgeSourceVersionModel:
        version = session.scalar(
            select(KnowledgeSourceVersionModel).where(
                KnowledgeSourceVersionModel.source_id == source_id,
                KnowledgeSourceVersionModel.version_number == 1,
            )
        )
        if version is None:
            raise UploadPolicyUnavailable
        return version

    def _quota(
        self,
        session: Session,
        actor_id: UUID,
        quota_day: date,
        policy: KnowledgeUploadPolicyModel,
    ) -> QuotaSnapshot:
        return QuotaSnapshot(
            timezone=policy.quota_timezone,
            daily_limit=policy.daily_success_limit,
            daily_used=self._count(
                session,
                actor_id,
                statuses=("STORED",),
                quota_day=quota_day,
            ),
            effective_source_limit=policy.effective_source_limit,
            effective_source_count=self._count(
                session,
                actor_id,
                statuses=("STORED",),
            ),
        )

    @staticmethod
    def _count(
        session: Session,
        actor_id: UUID,
        *,
        statuses: tuple[str, ...],
        quota_day: date | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(KnowledgeSourceModel)
            .where(
                KnowledgeSourceModel.owner_user_id == actor_id,
                KnowledgeSourceModel.ingestion_status.in_(statuses),
            )
        )
        if quota_day is not None:
            statement = statement.where(KnowledgeSourceModel.quota_day == quota_day)
        return int(session.scalar(statement) or 0)
