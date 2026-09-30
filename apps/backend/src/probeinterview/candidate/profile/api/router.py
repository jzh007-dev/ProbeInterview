"""Current actor profile overview and target profile routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from probeinterview.candidate.profile.api.contracts import (
    DefaultTargetProfileRequest,
    ProfileOverviewResource,
    TargetProfileResource,
)
from probeinterview.candidate.profile.application.overview import GetProfileOverview
from probeinterview.candidate.profile.application.target_profile import (
    SetDefaultTargetProfile,
)
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


@router.put(
    "/api/v1/me/default-target-profile",
    response_model=TargetProfileResource,
)
def put_default_target_profile(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    payload: DefaultTargetProfileRequest,
) -> TargetProfileResource:
    """Create or update the calling actor's default target profile."""

    service: SetDefaultTargetProfile = request.app.state.default_target_profile_service
    profile = service.execute(
        actor,
        payload.target_role,
        payload.relevant_experience_months,
    )
    return TargetProfileResource(
        id=profile.id,
        target_role=profile.target_role,
        relevant_experience_months=profile.relevant_experience_months,
    )
