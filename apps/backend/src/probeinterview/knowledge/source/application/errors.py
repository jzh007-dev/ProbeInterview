"""Stable knowledge-source application failures."""

from dataclasses import dataclass

from probeinterview.knowledge.source.application.contracts import QuotaSnapshot


@dataclass(frozen=True, slots=True)
class FieldError:
    """Field-level safe validation detail."""

    field: str
    message: str
    code: str


class KnowledgeSourceError(Exception):
    """Base error mapped to RFC 9457 at the API boundary."""

    status: int = 500
    code: str = "knowledge_source_error"
    title: str = "Knowledge Source Error"
    detail: str = "The knowledge source request could not be completed."

    def __init__(
        self,
        *,
        errors: tuple[FieldError, ...] = (),
        quota: QuotaSnapshot | None = None,
    ) -> None:
        super().__init__(self.code)
        self.errors = errors
        self.quota = quota


class InvalidUpload(KnowledgeSourceError):
    status = 400
    code = "invalid_knowledge_source"
    title = "Invalid Knowledge Source"
    detail = "The selected Markdown file is invalid."


class UploadTooLarge(InvalidUpload):
    status = 413
    code = "knowledge_source_too_large"
    title = "Knowledge Source Too Large"
    detail = "The Markdown file must be smaller than 500 KiB."


class PublicUploadForbidden(KnowledgeSourceError):
    status = 403
    code = "public_knowledge_source_forbidden"
    title = "Public Knowledge Source Forbidden"
    detail = "The current user cannot submit public knowledge sources."


class IdempotencyConflict(KnowledgeSourceError):
    status = 409
    code = "idempotency_conflict"
    title = "Idempotency Conflict"
    detail = "The Idempotency-Key is already bound to different upload input."


class EffectiveSourceLimitReached(KnowledgeSourceError):
    status = 409
    code = "effective_source_limit_reached"
    title = "Knowledge Source Limit Reached"
    detail = "The effective knowledge source limit has been reached."


class DailyUploadLimitReached(KnowledgeSourceError):
    status = 429
    code = "daily_upload_limit_reached"
    title = "Daily Upload Limit Reached"
    detail = "The daily knowledge source upload limit has been reached."


class UploadInProgress(KnowledgeSourceError):
    status = 409
    code = "knowledge_source_upload_in_progress"
    title = "Knowledge Source Upload In Progress"
    detail = "An identical knowledge source upload is already in progress."


class UploadPolicyUnavailable(KnowledgeSourceError):
    status = 500
    code = "knowledge_upload_policy_unavailable"
    title = "Knowledge Upload Policy Unavailable"
    detail = "The current user's upload policy is unavailable."


class ObjectStorageUnavailable(KnowledgeSourceError):
    status = 503
    code = "object_storage_unavailable"
    title = "Object Storage Unavailable"
    detail = "The knowledge source could not be stored. Please retry."


class UploadFinalizationFailed(KnowledgeSourceError):
    status = 503
    code = "knowledge_source_finalization_failed"
    title = "Knowledge Source Finalization Failed"
    detail = "The stored source could not be finalized. Please retry."
