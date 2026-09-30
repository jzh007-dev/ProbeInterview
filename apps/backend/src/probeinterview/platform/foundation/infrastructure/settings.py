"""Typed runtime configuration and startup validation."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AuthenticationMode = Literal["wechat", "local_test"]
WeChatAdapter = Literal["real", "fake"]
ObjectStorageAdapter = Literal["fake", "oss"]
ModelAdapter = Literal["fake", "bailian"]


def _is_blank(value: str | SecretStr | None) -> bool:
    if value is None:
        return True
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return not value.strip()


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

    authentication_mode: AuthenticationMode = "wechat"
    local_actor_id: UUID | None = None
    wechat_adapter: WeChatAdapter = "fake"
    wechat_app_id: str | None = None
    wechat_app_secret: SecretStr | None = None
    demo_profile_seed_enabled: bool = False
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
        if self.authentication_mode == "local_test":
            if self.environment == "production":
                raise ValueError("production forbids local_test authentication")
            if self.environment != "test":
                raise ValueError("local_test authentication requires test environment")
            if self.local_actor_id is None:
                raise ValueError("local_test authentication requires local_actor_id")
            if not _is_blank(self.wechat_app_id) or not _is_blank(self.wechat_app_secret):
                raise ValueError("local_test authentication forbids WeChat settings")
        else:
            if self.local_actor_id is not None:
                raise ValueError("wechat authentication forbids local_actor_id")
            if _is_blank(self.wechat_app_id):
                raise ValueError("wechat authentication requires wechat_app_id")
            if self.wechat_adapter == "real" and _is_blank(self.wechat_app_secret):
                raise ValueError("real WeChat adapter requires wechat_app_secret")
            if self.wechat_adapter == "fake" and not _is_blank(self.wechat_app_secret):
                raise ValueError("fake WeChat adapter forbids wechat_app_secret")

        if self.environment != "production":
            return self

        if self.wechat_adapter != "real":
            raise ValueError("production requires real WeChat adapter")

        if self.demo_profile_seed_enabled:
            raise ValueError("production forbids demo profile seed")

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
                if _is_blank(getattr(self, field_name)):
                    missing.append(field_name)

        if (
            self.embedding_adapter == "bailian" or self.structured_llm_adapter == "bailian"
        ) and _is_blank(self.bailian_api_key):
            missing.append("bailian_api_key")

        if missing:
            raise ValueError(f"missing production adapter settings: {', '.join(sorted(missing))}")

        return self
