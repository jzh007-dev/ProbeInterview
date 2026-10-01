"""Dev-only display surface for fake-storage objects.

The fake adapter keeps objects in process memory, so a signed URL can only
resolve against the API process itself. The route re-checks the signed
expiry on every request — the same guarantee a real object-storage host
would enforce — and never runs in production, which forbids the fake
adapter entirely.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import Response

from probeinterview.platform.foundation.infrastructure.object_storage import (
    FakeObjectStorage,
)

router = APIRouter()


@router.get("/local-objects/{object_key:path}")
def read_local_object(
    request: Request,
    object_key: str,
    expires_at: Annotated[str | None, Query()] = None,
) -> Response:
    """Serve one fake-storage object while its signed lifetime is valid."""

    if expires_at is None:
        raise HTTPException(status_code=403)
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        raise HTTPException(status_code=403) from None
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= datetime.now(UTC):
        raise HTTPException(status_code=403)

    storage = request.app.state.object_storage
    if not isinstance(storage, FakeObjectStorage):  # pragma: no cover - mount guard
        raise HTTPException(status_code=404)
    stored = storage.get(object_key)
    if stored is None:
        raise HTTPException(status_code=404)
    return Response(
        content=stored.content,
        media_type=stored.content_type,
        headers={"Cache-Control": "private, no-store"},
    )
