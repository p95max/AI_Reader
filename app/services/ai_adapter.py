"""Shared OpenAI adapter for adapting technical PDF blocks into narration."""

import base64
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings, get_settings


class AIAdapterError(RuntimeError):
    """Raised when the AI provider cannot produce usable narration."""


class AIResponseError(AIAdapterError):
    """Raised when a provider response does not include narration text."""


@dataclass(frozen=True)
class AIRequest:
    instructions: str
    input_text: str
    max_output_tokens: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    model: str | None = None
    images: tuple[ImageInput, ...] = ()


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str = "image/png"

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Image input cannot be empty")

    @property
    def data_url(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class UsageCost:
    input_cost: float
    cached_input_cost: float
    output_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.cached_input_cost + self.output_cost


@dataclass(frozen=True)
class AIResponse:
    text: str
    model: str
    usage: TokenUsage
    cost: UsageCost
    provider_response_id: str | None
    cached: bool = False


class AIAdapter(Protocol):
    async def generate(self, request: AIRequest) -> AIResponse: ...


class UsageReporter(Protocol):
    def record(self, request: AIRequest, response: AIResponse) -> None: ...


class StructuredUsageReporter:
    """Writes request cost and token usage without logging user content."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger(__name__)

    def record(self, request: AIRequest, response: AIResponse) -> None:
        self._logger.info(
            "ai_usage_recorded",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            cached_input_tokens=response.usage.cached_input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            total_cost=response.cost.total_cost,
            metadata=request.metadata,
        )


class ResponsesClient(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class OpenAIClient(Protocol):
    responses: ResponsesClient


RetryableProviderError = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
    ConnectionError,
    TimeoutError,
)


class OpenAIAdapter:
    """Reliable implementation of the shared AI adapter using Responses API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: OpenAIClient | None = None,
        usage_reporter: UsageReporter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if client is None:
            api_key = self._settings.openai_api_key
            if api_key is None:
                raise AIAdapterError("AI_READER_OPENAI_API_KEY must be configured")
            client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                timeout=self._settings.ai_timeout_seconds,
                max_retries=0,
            )
        self._client = client
        self._usage_reporter = usage_reporter or StructuredUsageReporter()

    async def generate(self, request: AIRequest) -> AIResponse:
        provider_response = await self._create_response(request)
        text = str(getattr(provider_response, "output_text", "")).strip()
        if not text:
            raise AIResponseError("AI provider returned an empty narration")

        usage = self._extract_usage(getattr(provider_response, "usage", None))
        response = AIResponse(
            text=text,
            model=request.model or self._settings.ai_model,
            usage=usage,
            cost=self._calculate_cost(usage),
            provider_response_id=getattr(provider_response, "id", None),
        )
        self._usage_reporter.record(request, response)
        return response

    async def _create_response(self, request: AIRequest) -> Any:
        request_kwargs: dict[str, Any] = {
            "model": request.model or self._settings.ai_model,
            "instructions": request.instructions,
            "input": self._response_input(request),
        }
        if request.max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = request.max_output_tokens
        if request.metadata:
            request_kwargs["metadata"] = request.metadata

        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._settings.ai_max_attempts),
            wait=wait_exponential(
                multiplier=self._settings.ai_retry_wait_seconds,
                max=self._settings.ai_retry_max_wait_seconds,
            ),
            retry=retry_if_exception_type(RetryableProviderError),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                return await self._client.responses.create(**request_kwargs)
        raise AssertionError("Retry loop did not return or raise")

    @staticmethod
    def _response_input(request: AIRequest) -> str | list[dict[str, Any]]:
        if not request.images:
            return request.input_text

        content: list[dict[str, str]] = [{"type": "input_text", "text": request.input_text}]
        content.extend(
            {"type": "input_image", "image_url": image.data_url} for image in request.images
        )
        return [{"role": "user", "content": content}]

    @staticmethod
    def _extract_usage(raw_usage: Any) -> TokenUsage:
        input_details = getattr(raw_usage, "input_tokens_details", None)
        return TokenUsage(
            input_tokens=int(getattr(raw_usage, "input_tokens", 0) or 0),
            cached_input_tokens=int(getattr(input_details, "cached_tokens", 0) or 0),
            output_tokens=int(getattr(raw_usage, "output_tokens", 0) or 0),
        )

    def _calculate_cost(self, usage: TokenUsage) -> UsageCost:
        uncached_input_tokens = max(usage.input_tokens - usage.cached_input_tokens, 0)
        return UsageCost(
            input_cost=(
                uncached_input_tokens * self._settings.ai_input_cost_per_million_tokens / 1_000_000
            ),
            cached_input_cost=(
                usage.cached_input_tokens
                * self._settings.ai_cached_input_cost_per_million_tokens
                / 1_000_000
            ),
            output_cost=(
                usage.output_tokens * self._settings.ai_output_cost_per_million_tokens / 1_000_000
            ),
        )
