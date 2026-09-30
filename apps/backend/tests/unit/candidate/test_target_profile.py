"""Default target profile validation and actor-scoped write invariants."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from probeinterview.candidate.profile.api.contracts import (
    DefaultTargetProfileRequest,
)
from probeinterview.candidate.profile.application.contracts import (
    TargetProfileOverview,
)
from probeinterview.candidate.profile.application.target_profile import (
    SetDefaultTargetProfile,
    TargetProfileFieldInvalid,
    validate_target_role,
)
from probeinterview.identity.access.domain.context import ActorContext

ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")


def test_target_role_is_trimmed_and_length_bounded() -> None:
    assert validate_target_role("  后端工程师  ") == "后端工程师"
    assert validate_target_role("x" * 200) == "x" * 200


@pytest.mark.parametrize(
    ("target_role", "message_part"),
    [
        ("", "non-empty"),
        ("   ", "non-empty"),
        ("x" * 201, "at most 200"),
        ("角色\x1b", "control characters"),
        ("角色\x7f", "control characters"),
    ],
)
def test_invalid_target_roles_raise_field_errors(
    target_role: str,
    message_part: str,
) -> None:
    with pytest.raises(TargetProfileFieldInvalid) as error:
        validate_target_role(target_role)

    assert error.value.field == "target_role"
    assert error.value.code == "invalid_target_role"
    assert message_part in error.value.message


def test_execute_scopes_the_write_to_the_authenticated_actor_only() -> None:
    store = StubStore()
    service = SetDefaultTargetProfile(store)

    profile = service.execute(
        ActorContext(actor_id=ACTOR_ID, capabilities=frozenset()),
        "  平台工程师 ",
        36,
    )

    assert store.actor_ids == [ACTOR_ID]
    assert store.writes[0].target_role == "平台工程师"
    assert store.writes[0].relevant_experience_months == 36
    assert profile == store.returned


def test_request_contract_rejects_forged_profile_identifiers() -> None:
    with pytest.raises(ValidationError) as error:
        DefaultTargetProfileRequest(
            profile_id=str(uuid4()),
            target_role="平台工程师",
            relevant_experience_months=36,
        )

    assert any("profile_id" in str(item["loc"]) for item in error.value.errors())


def test_request_contract_bounds_experience_months() -> None:
    for months in (-1, 601):
        with pytest.raises(ValidationError):
            DefaultTargetProfileRequest(
                target_role="平台工程师",
                relevant_experience_months=months,
            )

    valid = DefaultTargetProfileRequest(
        target_role="平台工程师",
        relevant_experience_months=600,
    )
    assert valid.relevant_experience_months == 600


class StubStore:
    def __init__(self) -> None:
        self.actor_ids: list[UUID] = []
        self.writes: list[object] = []
        self.returned = TargetProfileOverview(
            id=uuid4(),
            target_role="平台工程师",
            relevant_experience_months=36,
        )

    def upsert_default(self, actor_id: UUID, write: object) -> TargetProfileOverview:
        self.actor_ids.append(actor_id)
        self.writes.append(write)
        return self.returned
