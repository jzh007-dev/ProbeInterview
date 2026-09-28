"""Typed runtime configuration and startup validation."""

from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
ObjectStorageAdapter = Literal["fake", "oss"]
ModelAdapter = Literal["fake", "bailian"]


class Settings(BaseSettings):
    """Configuration shared by the API and worker processes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROBEINTERVIEW_",
        extra="ignore",
    )

    environment: Environment = "development"
    database_url: str = Field(min_length=1)
    celery_broker_url: str = Field(min_length=1)

    local_actor_enabled: bool = True
    foundation_probe_enabled: bool = True

    object_storage_adapter: ObjectStorageAdapter = "fake"
    embedding_adapter: ModelAdapter = "fake"
    structured_llm_adapter: ModelAdapter = "fake"

    oss_endpoint: str | None = None
    oss_bucket: str | None = None
    oss_access_key_id: str | None = None
    oss_access_key_secret: SecretStr | None = None
    bailian_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_production_boundaries(self) -> Self:
        if self.environment != "production":
            return self

        if self.local_actor_enabled:
            raise ValueError("production forbids local actor")

        fake_adapters = {
            self.object_storage_adapter,
            self.embedding_adapter,
            self.structured_llm_adapter,
        }
        if "fake" in fake_adapters:
            raise ValueError("production forbids fake adapters")

        if self.foundation_probe_enabled:
            raise ValueError("production forbids foundation probe")

        missing: list[str] = []
        if self.object_storage_adapter == "oss":
            for field_name in (
                "oss_endpoint",
                "oss_bucket",
                "oss_access_key_id",
                "oss_access_key_secret",
            ):
                if getattr(self, field_name) is None:
                    missing.append(field_name)

        if (
            self.embedding_adapter == "bailian" or self.structured_llm_adapter == "bailian"
        ) and self.bailian_api_key is None:
            missing.append("bailian_api_key")

        if missing:
            raise ValueError(f"missing production adapter settings: {', '.join(sorted(missing))}")

        return self
