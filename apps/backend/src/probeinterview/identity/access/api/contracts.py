"""Typed WeChat authentication bootstrap HTTP resources."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from probeinterview.identity.access.application.exchange import (
    AuthenticatedExchange,
    ExchangeSnapshot,
    RegistrationRequired,
)


class WeChatExchangeRequest(BaseModel):
    """One transient WeChat login code."""

    code: str = Field(min_length=1, max_length=255)


class WeChatRegistrationRequest(BaseModel):
    """One-time registration credential plus the display-safe nickname."""

    registration_token: str = Field(min_length=1, max_length=255)
    nickname: str = Field(min_length=1, max_length=200)


class ExchangeTargetProfileResource(BaseModel):
    """Display-safe summary of the default target profile."""

    target_role: str
    relevant_experience_months: int


class CurrentUserResource(BaseModel):
    """Server-truth display snapshot for the authenticated user."""

    id: UUID
    nickname: str
    avatar_url: str | None
    avatar_url_expires_at: datetime | None
    default_target_profile: ExchangeTargetProfileResource | None

    @classmethod
    def from_snapshot(cls, snapshot: ExchangeSnapshot) -> "CurrentUserResource":
        """Build the resource from an application snapshot.

        Object keys are never exposed; custom avatars become signed URLs in
        the later display change.
        """

        profile = snapshot.default_target_profile
        return cls(
            id=snapshot.user_id,
            nickname=snapshot.nickname,
            avatar_url=None,
            avatar_url_expires_at=None,
            default_target_profile=(
                ExchangeTargetProfileResource(
                    target_role=profile.target_role,
                    relevant_experience_months=profile.relevant_experience_months,
                )
                if profile is not None
                else None
            ),
        )


class AuthenticatedExchangeResource(BaseModel):
    """A new bearer session and the current-user snapshot."""

    status: Literal["authenticated"]
    access_token: str
    token_type: Literal["Bearer"]
    expires_at: datetime
    current_user: CurrentUserResource

    @classmethod
    def from_application(cls, result: AuthenticatedExchange) -> "AuthenticatedExchangeResource":
        """Build the resource from the application result."""

        return cls(
            status="authenticated",
            access_token=result.access_token,
            token_type="Bearer",
            expires_at=result.expires_at,
            current_user=CurrentUserResource.from_snapshot(result.current_user),
        )


class RegistrationRequiredResource(BaseModel):
    """A short-lived one-time credential for first registration."""

    status: Literal["registration_required"]
    registration_token: str
    expires_at: datetime

    @classmethod
    def from_application(cls, result: RegistrationRequired) -> "RegistrationRequiredResource":
        """Build the resource from the application result."""

        return cls(
            status="registration_required",
            registration_token=result.registration_token,
            expires_at=result.expires_at,
        )
