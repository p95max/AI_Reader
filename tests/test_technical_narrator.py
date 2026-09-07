from dataclasses import dataclass, field

import pytest

from app.services.ai_adapter import AIRequest, AIResponse, TokenUsage, UsageCost
from app.services.pdf_parser import FormulaBlock, TableBlock, TextBlock
from app.services.technical_narrator import TechnicalNarrator


@dataclass
class RecordingAdapter:
    requests: list[AIRequest] = field(default_factory=list)

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(
            text="Spoken narration",
            model="test-model",
            usage=TokenUsage(),
            cost=UsageCost(input_cost=0, cached_input_cost=0, output_cost=0),
            provider_response_id="response",
        )


def code_block() -> TextBlock:
    return TextBlock(
        page_number=3,
        text="def total(items):\n    return sum(items)",
        bbox=(0, 0, 100, 20),
        font_size=10,
        is_heading=False,
        is_code=True,
    )


@pytest.mark.asyncio
async def test_narrator_builds_code_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)

    response = await narrator.narrate_code(code_block())

    assert response.text == "Spoken narration"
    request = adapter.requests[0]
    assert request.metadata == {"block_type": "code", "page_number": "3"}
    assert request.input_text.startswith("def total")
    assert "Не читай синтаксис посимвольно" in request.instructions


@pytest.mark.asyncio
async def test_narrator_builds_table_request_without_losing_empty_cells() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    table = TableBlock(
        page_number=4,
        bbox=(0, 0, 100, 50),
        cells=(("Metric", "Value"), ("Pages", "42"), ("Notes", "")),
    )

    await narrator.narrate_table(table)

    request = adapter.requests[0]
    assert request.metadata == {"block_type": "table", "page_number": "4"}
    assert request.input_text == "Таблица:\nMetric | Value\nPages | 42\nNotes | (пусто)"
    assert "Не придумывай значения" in request.instructions


@pytest.mark.asyncio
async def test_narrator_builds_formula_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    formula = FormulaBlock(page_number=5, text="E = m * c^2", bbox=(0, 0, 100, 20))

    await narrator.narrate_formula(formula)

    request = adapter.requests[0]
    assert request.metadata == {"block_type": "formula", "page_number": "5"}
    assert request.input_text == "E = m * c^2"
    assert "объясни смысл связи" in request.instructions.lower()
