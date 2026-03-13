from functools import lru_cache
from typing import ClassVar, Literal, final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@final
class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    PORT: int = Field(default=8000, ge=1, le=65535)
    HOST: str = "0.0.0.0"
    NAMESPACE: str = "default"
    KUBECONFIG_PATH: str | None = None

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return str(value).upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()
