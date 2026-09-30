"""Typed public knowledge-source resources."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from probeinterview.knowledge.source.application.contracts import (
    KnowledgeSourceCollection,
    KnowledgeSourceItem,
    KnowledgeSourceUpload,
    QuotaSnapshot,
)


class KnowledgeSourceQuotaResource(BaseModel):
    """Current actor's database-backed quota context."""

    timezone: Literal["Asia/Shanghai"]
    daily_limit: int
    daily_used: int
    effective_source_limit: int
    effective_source_count: int

    @classmethod
    def from_application(cls, quota: QuotaSnapshot) -> "KnowledgeSourceQuotaResource":
        return cls.model_validate(quota, from_attributes=True)


class KnowledgeSourceResource(BaseModel):
    """Display-safe source fields only."""

    id: UUID
    original_filename: str
    scope: Literal["PRIVATE", "PUBLIC"]
    processing_status: Literal["PENDING_EXTRACTION"]
    uploaded_at: datetime

    @classmethod
    def from_application(cls, item: KnowledgeSourceItem) -> "KnowledgeSourceResource":
        return cls.model_validate(item, from_attributes=True)


class KnowledgeSourceUploadResource(BaseModel):
    """Accepted upload response."""

    source: KnowledgeSourceResource
    quota: KnowledgeSourceQuotaResource

    @classmethod
    def from_application(
        cls,
        result: KnowledgeSourceUpload,
    ) -> "KnowledgeSourceUploadResource":
        return cls(
            source=KnowledgeSourceResource.from_application(result.source),
            quota=KnowledgeSourceQuotaResource.from_application(result.quota),
        )


class KnowledgeSourceCollectionResource(BaseModel):
    """Owner-scoped list response."""

    quota: KnowledgeSourceQuotaResource
    items: list[KnowledgeSourceResource]

    @classmethod
    def from_application(
        cls,
        result: KnowledgeSourceCollection,
    ) -> "KnowledgeSourceCollectionResource":
        return cls(
            quota=KnowledgeSourceQuotaResource.from_application(result.quota),
            items=[KnowledgeSourceResource.from_application(item) for item in result.items],
        )
