"""Deterministic fake and real WeChat identity adapters."""

from typing import Literal

import httpx

from probeinterview.identity.access.application.wechat import (
    WeChatCodeExchangeFailed,
    WeChatIdentity,
    WeChatIdentityExchange,
    WeChatServiceUnavailable,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
_REAL_TIMEOUT_SECONDS = 5.0
_RETRYABLE_ERROR_CODES = {-1, 45011}


class FakeWeChatAdapter:
    """Deterministic identity mapping for development and test.

    Code conventions:
    - ``<openid>`` resolves to that identity without a unionid;
    - ``<openid>+unionid:<unionid>`` resolves with the unionid;
    - ``invalid-code`` and ``used-code`` mirror rejected codes;
    - ``timeout-code`` and ``unavailable-code`` mirror provider outages.
    """

    _rejected_codes = frozenset({"invalid-code", "used-code"})
    _unavailable_codes = frozenset({"timeout-code", "unavailable-code"})

    def exchange(self, code: str) -> WeChatIdentity:
        """Map one deterministic code to a provider-neutral identity."""

        normalized = code.strip()
        if not normalized or normalized in self._rejected_codes:
            raise WeChatCodeExchangeFailed
        if normalized in self._unavailable_codes:
            raise WeChatServiceUnavailable
        openid, unionid_marker, unionid = normalized.partition("+unionid:")
        return WeChatIdentity(
            openid=openid,
            unionid=unionid if unionid_marker and unionid else None,
        )


class RealWeChatAdapter:
    """Call WeChat code2Session with bounded timeouts and safe error mapping."""

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._http_client = http_client or httpx.Client(
            timeout=httpx.Timeout(_REAL_TIMEOUT_SECONDS)
        )

    def exchange(self, code: str) -> WeChatIdentity:
        """Return the identity or raise a safe application error."""

        try:
            response = self._http_client.get(
                _CODE2SESSION_URL,
                params={
                    "appid": self._app_id,
                    "secret": self._app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
        except httpx.HTTPError:
            raise WeChatServiceUnavailable from None

        if response.status_code >= 500:
            raise WeChatServiceUnavailable
        if response.status_code != 200:
            raise WeChatCodeExchangeFailed
        try:
            payload = response.json()
        except ValueError:
            raise WeChatCodeExchangeFailed from None

        errcode = payload.get("errcode", 0)
        openid = payload.get("openid")
        if errcode == 0 and isinstance(openid, str) and openid:
            unionid = payload.get("unionid")
            return WeChatIdentity(
                openid=openid,
                unionid=unionid if isinstance(unionid, str) and unionid else None,
            )
        if errcode in _RETRYABLE_ERROR_CODES:
            raise WeChatServiceUnavailable
        raise WeChatCodeExchangeFailed


def build_wechat_exchange(
    settings: Settings,
    adapter: Literal["fake", "real"] | None = None,
) -> WeChatIdentityExchange:
    """Build the configured WeChat identity exchange adapter."""

    resolved_adapter = adapter or settings.wechat_adapter
    if resolved_adapter == "fake":
        return FakeWeChatAdapter()
    if settings.wechat_app_id is None or settings.wechat_app_secret is None:
        raise ValueError("real WeChat adapter requires app id and secret")
    return RealWeChatAdapter(
        app_id=settings.wechat_app_id,
        app_secret=settings.wechat_app_secret.get_secret_value(),
    )
