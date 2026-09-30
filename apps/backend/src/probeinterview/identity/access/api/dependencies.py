"""FastAPI dependency for structured bearer authentication."""

import re

from fastapi import Request

from probeinterview.identity.access.application.actors import ActorAuthenticator
from probeinterview.identity.access.domain.context import ActorContext

# Opaque tokens are URL-safe base64; the bound only rejects junk before a
# digest is ever computed, never validates the token itself.
_BEARER_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]{1,512}$")
_BEARER_SCHEME = "bearer"


class AuthenticationRequired(Exception):
    """Raised when the request carries no resolvable bearer session."""


def extract_bearer_token(authorization: str | None) -> str | None:
    """Return the credential from a well-formed Bearer header without I/O."""

    if not authorization:
        return None
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != _BEARER_SCHEME:
        return None
    token = credentials.strip()
    if not token or not _BEARER_TOKEN_PATTERN.fullmatch(token):
        return None
    return token


def current_actor(request: Request) -> ActorContext:
    """Resolve the bearer session or reject the request before any handler."""

    authenticator: ActorAuthenticator = request.app.state.actor_authenticator
    actor = authenticator.authenticate(extract_bearer_token(request.headers.get("Authorization")))
    if actor is None:
        raise AuthenticationRequired
    return actor
