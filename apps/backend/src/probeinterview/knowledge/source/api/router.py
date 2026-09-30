"""Current actor Markdown upload and owner collection routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from probeinterview.identity.access.api.dependencies import current_actor
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.knowledge.source.api.contracts import (
    KnowledgeSourceCollectionResource,
    KnowledgeSourceUploadResource,
)
from probeinterview.knowledge.source.application.service import KnowledgeSourceService
from probeinterview.knowledge.source.application.validation import MAX_MARKDOWN_BYTES

router = APIRouter()


@router.post(
    "/api/v1/me/knowledge-sources",
    response_model=KnowledgeSourceUploadResource,
    status_code=202,
)
async def upload_knowledge_source(
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(current_actor)],
    file: Annotated[UploadFile, File()],
    scope: Annotated[str | None, Form()] = None,
    original_filename: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> KnowledgeSourceUploadResource:
    """Read one bounded upload and persist it through the application service."""

    content = await file.read(MAX_MARKDOWN_BYTES)
    await file.close()
    service: KnowledgeSourceService = request.app.state.knowledge_source_service
    result = await run_in_threadpool(
        service.upload,
        actor=actor,
        filename=file.filename,
        original_filename=original_filename,
        content=content,
        scope_value=scope,
        idempotency_key=idempotency_key,
    )
    response.headers["Location"] = "/api/v1/me/knowledge-sources"
    return KnowledgeSourceUploadResource.from_application(result)


@router.get(
    "/api/v1/me/knowledge-sources",
    response_model=KnowledgeSourceCollectionResource,
)
async def list_knowledge_sources(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> KnowledgeSourceCollectionResource:
    """Return only stored sources owned by the current actor."""

    service: KnowledgeSourceService = request.app.state.knowledge_source_service
    result = await run_in_threadpool(service.list_for_actor, actor)
    return KnowledgeSourceCollectionResource.from_application(result)
