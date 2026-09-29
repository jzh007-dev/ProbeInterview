"""ORM mapping contract tests for the profile overview modules."""

from importlib import import_module
from importlib.util import find_spec

from probeinterview.platform.foundation.infrastructure.persistence import Base


def test_identity_and_profile_modules_register_owned_tables() -> None:
    """Removing either module's mappings must make its owned tables disappear."""

    identity_module = "probeinterview.identity.access.infrastructure.models"
    profile_module = "probeinterview.candidate.profile.infrastructure.models"
    assert find_spec(identity_module) is not None
    assert find_spec(profile_module) is not None

    import_module(identity_module)
    import_module(profile_module)

    assert {"users", "wechat_identities"}.issubset(Base.metadata.tables)
    assert {"candidate_profiles", "user_resume"}.issubset(Base.metadata.tables)


def test_resume_mapping_contains_only_storage_neutral_metadata() -> None:
    """Provider details or file bytes must never become ORM columns."""

    profile_module = "probeinterview.candidate.profile.infrastructure.models"
    assert find_spec(profile_module) is not None
    import_module(profile_module)

    assert set(Base.metadata.tables["user_resume"].columns.keys()) == {
        "id",
        "user_id",
        "original_file_name",
        "media_type",
        "size_bytes",
        "content_sha256",
        "storage_object_key",
        "revision",
        "uploaded_at",
        "updated_at",
    }
