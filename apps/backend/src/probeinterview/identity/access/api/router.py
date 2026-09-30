"""Public WeChat authentication bootstrap routes."""

from fastapi import APIRouter, Request

from probeinterview.identity.access.api.contracts import (
    AuthenticatedExchangeResource,
    RegistrationRequiredResource,
    WeChatExchangeRequest,
)
from probeinterview.identity.access.application.exchange import (
    AuthenticatedExchange,
    WeChatExchangeService,
)

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
