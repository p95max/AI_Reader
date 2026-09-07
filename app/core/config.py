from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Reader API"
    environment: Literal["local", "development", "staging", "production"] = "local"
    debug: bool = False
    database_url: str = "postgresql+psycopg://ai_reader:ai_reader@localhost:5433/ai_reader"
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_READER_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
