from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelPricing(BaseModel):
    """Versioned price list entry, expressed in USD per one million tokens."""

    input_per_million_tokens: float = Field(default=0.0, ge=0)
    cached_input_per_million_tokens: float = Field(default=0.0, ge=0)
    output_per_million_tokens: float = Field(default=0.0, ge=0)
    version: str = Field(default="default", min_length=1, max_length=100)


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
    max_pdf_pages: int = Field(default=500, ge=1)
    upload_rate_limit: str = "5/minute"
    process_rate_limit: str = "10/minute"
    openai_api_key: SecretStr | None = None
    ai_model: str = "gpt-5.6-luna"
    ai_timeout_seconds: float = Field(default=45.0, gt=0)
    ai_max_attempts: int = Field(default=3, ge=1)
    ai_retry_wait_seconds: float = Field(default=1.0, ge=0)
    ai_retry_max_wait_seconds: float = Field(default=8.0, ge=0)
    ai_input_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    ai_cached_input_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    ai_output_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    ai_pricing_version: str = Field(default="default", min_length=1, max_length=100)
    ai_model_price_list: dict[str, ModelPricing] = Field(default_factory=dict)
    narration_cache_ttl_seconds: int = Field(default=7 * 24 * 60 * 60, ge=1)
    # OpenAI TTS is the single supported synthesis backend. There is no local
    # model, CUDA configuration, or model download in the service image.
    tts_voice: str = "alloy"
    tts_instruction: str = "Говори ясно, естественно и спокойно."
    tts_openai_model: str = "gpt-4o-mini-tts"
    tts_openai_voice: str = "alloy"
    tts_openai_timeout_seconds: float = Field(default=60.0, gt=0)
    tts_openai_normal_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    tts_openai_slow_speed: float = Field(default=0.85, ge=0.25, le=4.0)
    tts_external_cost_per_audio_hour_usd: float = Field(default=0.0, ge=0)
    tts_chunk_max_characters: int = Field(default=1_200, ge=100)
    tts_max_attempts: int = Field(default=3, ge=1)
    progressive_priority_chapter_count: int = Field(default=2, ge=1)
    playback_min_ready_duration_seconds: int = Field(default=10 * 60, ge=60)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_READER_",
        extra="ignore",
    )

    def pricing_for_model(self, model: str | None = None) -> ModelPricing:
        """Resolve the configured model entry, retaining legacy env vars as a safe fallback."""
        resolved_model = model or self.ai_model
        configured = self.ai_model_price_list.get(resolved_model)
        if configured is not None:
            return configured
        return ModelPricing(
            input_per_million_tokens=self.ai_input_cost_per_million_tokens,
            cached_input_per_million_tokens=self.ai_cached_input_cost_per_million_tokens,
            output_per_million_tokens=self.ai_output_cost_per_million_tokens,
            version=self.ai_pricing_version,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
