"""WeChat identity exchange application boundary."""

from dataclasses import dataclass
from typing import Protocol


class WeChatCodeExchangeFailed(Exception):
    """WeChat rejected the login code as invalid, expired, or already used."""


class WeChatServiceUnavailable(Exception):
    """The WeChat identity service timed out or is unavailable."""


@dataclass(frozen=True, slots=True)
class WeChatIdentity:
    """Provider-neutral identity result.

    Transient provider values such as ``session_key`` never cross this port.
    """

    openid: str
    unionid: str | None


class WeChatIdentityExchange(Protocol):
    """Exchange one WeChat login code for a provider-neutral identity."""

    def exchange(self, code: str) -> WeChatIdentity:
        """Return the identity or raise a safe application error."""
