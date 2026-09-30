"""Deterministic fake and real WeChat adapter behavior."""

import httpx
import pytest

from probeinterview.identity.access.application.wechat import (
    WeChatCodeExchangeFailed,
    WeChatServiceUnavailable,
)
from probeinterview.identity.access.infrastructure.wechat_adapters import (
    FakeWeChatAdapter,
    RealWeChatAdapter,
    build_wechat_exchange,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

SECRET = "unit-test-app-secret"


def real_adapter(responder) -> RealWeChatAdapter:
    return RealWeChatAdapter(
        app_id="wx-unit-app",
        app_secret=SECRET,
        http_client=httpx.Client(transport=httpx.MockTransport(responder)),
    )


class TestFakeAdapter:
    def test_known_identity_resolves_without_unionid(self) -> None:
        identity = FakeWeChatAdapter().exchange("oProbeInterviewDemoOpenId01")

        assert identity.openid == "oProbeInterviewDemoOpenId01"
        assert identity.unionid is None

    def test_known_identity_resolves_with_unionid(self) -> None:
        identity = FakeWeChatAdapter().exchange("oOpenId+unionid:uUnion1")

        assert identity.openid == "oOpenId"
        assert identity.unionid == "uUnion1"

    def test_empty_unionid_marker_resolves_without_unionid(self) -> None:
        identity = FakeWeChatAdapter().exchange("oOpenId+unionid:")

        assert identity.unionid is None

    @pytest.mark.parametrize("code", ["invalid-code", "used-code", "", "   "])
    def test_rejected_codes_raise_exchange_failed(self, code: str) -> None:
        with pytest.raises(WeChatCodeExchangeFailed):
            FakeWeChatAdapter().exchange(code)

    @pytest.mark.parametrize("code", ["timeout-code", "unavailable-code"])
    def test_outage_codes_raise_service_unavailable(self, code: str) -> None:
        with pytest.raises(WeChatServiceUnavailable):
            FakeWeChatAdapter().exchange(code)


class TestRealAdapter:
    def test_success_returns_identity_with_optional_unionid(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"openid": "oRealOpenId", "unionid": "uRealUnion", "session_key": "sk"},
            )

        adapter = real_adapter(responder)
        identity = adapter.exchange("the-login-code")

        assert identity.openid == "oRealOpenId"
        assert identity.unionid == "uRealUnion"

    def test_request_carries_configured_app_credentials(self) -> None:
        captured: dict[str, str] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            captured.update(request.url.params)
            return httpx.Response(200, json={"openid": "oRealOpenId"})

        real_adapter(responder).exchange("the-login-code")

        assert captured["appid"] == "wx-unit-app"
        assert captured["secret"] == SECRET
        assert captured["js_code"] == "the-login-code"
        assert captured["grant_type"] == "authorization_code"

    @pytest.mark.parametrize("errcode", [40029, 40163, 41008])
    def test_rejected_errcodes_raise_exchange_failed(self, errcode: int) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"errcode": errcode, "errmsg": "raw provider detail"})

        with pytest.raises(WeChatCodeExchangeFailed) as error:
            real_adapter(responder).exchange("the-login-code")

        assert "raw provider detail" not in str(error.value)

    @pytest.mark.parametrize("errcode", [-1, 45011])
    def test_retryable_errcodes_raise_service_unavailable(self, errcode: int) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"errcode": errcode, "errmsg": "system busy"})

        with pytest.raises(WeChatServiceUnavailable):
            real_adapter(responder).exchange("the-login-code")

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    def test_provider_server_errors_raise_service_unavailable(self, status_code: int) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, json={})

        with pytest.raises(WeChatServiceUnavailable):
            real_adapter(responder).exchange("the-login-code")

    def test_transport_errors_raise_service_unavailable(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        with pytest.raises(WeChatServiceUnavailable) as error:
            real_adapter(responder).exchange("the-login-code")

        assert "the-login-code" not in str(error.value)

    def test_garbage_success_body_raises_exchange_failed(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-json")

        with pytest.raises(WeChatCodeExchangeFailed):
            real_adapter(responder).exchange("the-login-code")

    def test_non_200_client_error_raises_exchange_failed(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={})

        with pytest.raises(WeChatCodeExchangeFailed):
            real_adapter(responder).exchange("the-login-code")


def test_builder_selects_adapter_from_settings() -> None:
    fake_settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@postgres/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="fake",
        wechat_app_id="wx-app",
        _env_file=None,
    )
    assert isinstance(build_wechat_exchange(fake_settings), FakeWeChatAdapter)

    real_settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://probe:probe@postgres/probe",
        celery_broker_url="redis://redis:6379/0",
        authentication_mode="wechat",
        wechat_adapter="real",
        wechat_app_id="wx-app",
        wechat_app_secret=SECRET,
        _env_file=None,
    )
    assert isinstance(build_wechat_exchange(real_settings), RealWeChatAdapter)
