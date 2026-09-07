from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.ai_adapter import AIRequest, AIResponse, ImageInput, OpenAIAdapter


class FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        next_response = self._responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = FakeResponses(responses)


@dataclass
class RecordingUsageReporter:
    records: list[tuple[AIRequest, AIResponse]] = field(default_factory=list)

    def record(self, request: AIRequest, response: AIResponse) -> None:
        self.records.append((request, response))


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "openai_api_key": "test-key",
        "ai_model": "gpt-5.6-luna",
        "ai_max_attempts": 2,
        "ai_retry_wait_seconds": 0,
        "ai_retry_max_wait_seconds": 0,
        "ai_input_cost_per_million_tokens": 2.0,
        "ai_cached_input_cost_per_million_tokens": 0.5,
        "ai_output_cost_per_million_tokens": 4.0,
    }
    values.update(overrides)
    return Settings(**values)


def provider_response(text: str = "Narration") -> SimpleNamespace:
    return SimpleNamespace(
        id="resp_123",
        output_text=text,
        usage=SimpleNamespace(
            input_tokens=1_000,
            output_tokens=500,
            input_tokens_details=SimpleNamespace(cached_tokens=200),
        ),
    )


@pytest.mark.asyncio
async def test_openai_adapter_generates_narration_and_records_usage() -> None:
    client = FakeClient([provider_response()])
    reporter = RecordingUsageReporter()
    adapter = OpenAIAdapter(make_settings(), client=client, usage_reporter=reporter)
    request = AIRequest(
        instructions="Explain the code for listening.",
        input_text="def hello(): return 'world'",
        max_output_tokens=200,
        metadata={"block_type": "code"},
    )

    response = await adapter.generate(request)

    assert response.text == "Narration"
    assert response.model == "gpt-5.6-luna"
    assert response.usage.input_tokens == 1_000
    assert response.usage.cached_input_tokens == 200
    assert response.usage.output_tokens == 500
    assert response.cost.total_cost == pytest.approx(0.0037)
    assert client.responses.calls == [
        {
            "model": "gpt-5.6-luna",
            "instructions": "Explain the code for listening.",
            "input": "def hello(): return 'world'",
            "max_output_tokens": 200,
            "metadata": {"block_type": "code"},
        }
    ]
    assert reporter.records == [(request, response)]


@pytest.mark.asyncio
async def test_openai_adapter_retries_timeout_errors() -> None:
    client = FakeClient([TimeoutError("temporary failure"), provider_response("Recovered")])
    adapter = OpenAIAdapter(make_settings(), client=client)

    response = await adapter.generate(AIRequest(instructions="Narrate", input_text="A block"))

    assert response.text == "Recovered"
    assert len(client.responses.calls) == 2


@pytest.mark.asyncio
async def test_openai_adapter_sends_images_as_responses_vision_input() -> None:
    client = FakeClient([provider_response("Visual narration")])
    adapter = OpenAIAdapter(make_settings(), client=client)

    await adapter.generate(
        AIRequest(
            instructions="Describe image",
            input_text="Diagram context",
            images=(ImageInput(data=b"png-data"),),
        )
    )

    content = client.responses.calls[0]["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "Diagram context"}
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
