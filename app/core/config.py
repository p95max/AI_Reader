from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
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
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "ai-reader"
    s3_region_name: str = "us-east-1"
    max_pdf_size_bytes: int = 100 * 1024 * 1024
    openai_api_key: SecretStr | None = None
    ai_model: str = "gpt-5.6-luna"
    ai_timeout_seconds: float = Field(default=45.0, gt=0)
    ai_max_attempts: int = Field(default=3, ge=1)
    ai_retry_wait_seconds: float = Field(default=1.0, ge=0)
    ai_retry_max_wait_seconds: float = Field(default=8.0, ge=0)
    ai_input_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    ai_cached_input_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    ai_output_cost_per_million_tokens: float = Field(default=0.0, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_READER_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
