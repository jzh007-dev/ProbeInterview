"""Opaque credential generation and digest-only persistence helpers.

Tokens are 32 cryptographically random bytes encoded as URL-safe base64.
Only their SHA-256 digests are ever persisted; SHA-256 is sufficient because
the input carries 256 bits of server-generated entropy.
"""

import base64
import hashlib
import secrets
from datetime import timedelta

SESSION_TOKEN_BYTES = 32
REGISTRATION_TOKEN_BYTES = 32
SESSION_TTL = timedelta(days=30)
REGISTRATION_TOKEN_TTL = timedelta(minutes=10)


def new_session_token() -> str:
    """Return one opaque bearer token for response building only."""

    return _new_token(SESSION_TOKEN_BYTES)


def new_registration_token() -> str:
    """Return one short-lived one-time registration credential."""

    return _new_token(REGISTRATION_TOKEN_BYTES)


def token_digest(token: str) -> str:
    """Return the lowercase SHA-256 hex digest of one token."""

    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_token(length: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode("ascii")
