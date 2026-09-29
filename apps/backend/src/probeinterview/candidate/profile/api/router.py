"""Current actor profile overview route."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from probeinterview.candidate.profile.api.contracts import ProfileOverviewResource
from probeinterview.candidate.profile.application.overview import GetProfileOverview
from probeinterview.identity.access.api.dependencies import current_actor
from probeinterview.identity.access.domain.context import ActorContext

router = APIRouter()


@router.get("/api/v1/me/overview", response_model=ProfileOverviewResource)
def get_profile_overview(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ProfileOverviewResource:
    query: GetProfileOverview = request.app.state.profile_overview_query
    return ProfileOverviewResource.from_application(query.execute(actor))
