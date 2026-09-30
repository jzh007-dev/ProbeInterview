"""Opaque credential generation and digest-only persistence helpers."""

import base64
import hashlib
import re
from datetime import timedelta

from probeinterview.identity.access.application.tokens import (
    REGISTRATION_TOKEN_BYTES,
    REGISTRATION_TOKEN_TTL,
    SESSION_TOKEN_BYTES,
    SESSION_TTL,
    new_registration_token,
    new_session_token,
    token_digest,
)


def test_session_tokens_are_url_safe_base64_of_32_random_bytes() -> None:
    token = new_session_token()

    decoded = base64.urlsafe_b64decode(token)
    assert len(decoded) == SESSION_TOKEN_BYTES
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}=", token)


def test_registration_tokens_are_url_safe_base64_of_32_random_bytes() -> None:
    token = new_registration_token()

    decoded = base64.urlsafe_b64decode(token)
    assert len(decoded) == REGISTRATION_TOKEN_BYTES
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}=", token)


def test_tokens_are_individually_random() -> None:
    tokens = {new_session_token() for _ in range(200)}

    assert len(tokens) == 200


def test_token_digest_is_lowercase_sha256_hex() -> None:
    token = new_session_token()

    digest = token_digest(token)

    assert digest == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_different_tokens_produce_different_digests() -> None:
    assert token_digest(new_session_token()) != token_digest(new_session_token())


def test_time_to_live_boundaries_match_the_contract() -> None:
    assert SESSION_TTL.days == 30
    assert timedelta(minutes=10) == REGISTRATION_TOKEN_TTL
