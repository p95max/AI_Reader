from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Reader API"
    environment: Literal["local", "development", "staging", "production"] = "local"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_READER_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
