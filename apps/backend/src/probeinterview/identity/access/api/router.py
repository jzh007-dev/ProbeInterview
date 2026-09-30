"""Public WeChat authentication bootstrap routes."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile

from probeinterview.identity.access.api.contracts import (
    AuthenticatedExchangeResource,
    RegistrationRequiredResource,
    WeChatExchangeRequest,
    WeChatRegistrationRequest,
)
from probeinterview.identity.access.application.exchange import (
    AuthenticatedExchange,
    WeChatExchangeService,
)
from probeinterview.identity.access.application.registration import RegistrationService

router = APIRouter()


@router.post(
    "/api/v1/auth/wechat/exchanges",
    response_model=AuthenticatedExchangeResource | RegistrationRequiredResource,
)
def exchange_wechat_code(
    request: Request,
    payload: WeChatExchangeRequest,
) -> AuthenticatedExchangeResource | RegistrationRequiredResource:
    """Exchange one WeChat login code for a session or registration token."""

    service: WeChatExchangeService = request.app.state.wechat_exchange_service
    result = service.exchange(payload.code)
    if isinstance(result, AuthenticatedExchange):
        return AuthenticatedExchangeResource.from_application(result)
    return RegistrationRequiredResource.from_application(result)


@router.post(
    "/api/v1/auth/wechat/registrations",
    response_model=AuthenticatedExchangeResource,
)
def register_wechat_user(
    request: Request,
    payload: WeChatRegistrationRequest,
) -> AuthenticatedExchangeResource:
    """Complete first registration with the built-in default avatar."""

    service: RegistrationService = request.app.state.wechat_registration_service
    result = service.register(
        registration_token=payload.registration_token,
        nickname=payload.nickname,
    )
    return AuthenticatedExchangeResource.from_application(result)


@router.post(
    "/api/v1/auth/wechat/avatar-registrations",
    response_model=AuthenticatedExchangeResource,
)
async def register_wechat_user_with_avatar(
    request: Request,
    registration_token: Annotated[str, Form()],
    nickname: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> AuthenticatedExchangeResource:
    """Complete first registration with one custom private avatar."""

    service: RegistrationService = request.app.state.wechat_registration_service
    result = service.register(
        registration_token=registration_token,
        nickname=nickname,
        avatar_content=await file.read(),
        avatar_media_type=file.content_type,
    )
    return AuthenticatedExchangeResource.from_application(result)
