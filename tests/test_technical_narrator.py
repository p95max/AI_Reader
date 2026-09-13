from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from app.services.ai_adapter import AIRequest, AIResponse, TokenUsage, UsageContext, UsageCost
from app.services.pdf_parser import FormulaBlock, TableBlock, TextBlock, VisualBlock
from app.services.technical_narrator import (
    CodeMode,
    DiagramMode,
    FormulaMode,
    NarrationSettings,
    TableMode,
    TechnicalNarrator,
)
from app.services.visual_assets import VisualAsset


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


@dataclass
class MemoryNarrationCache:
    values: dict[str, str] = field(default_factory=dict)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, narration: str) -> None:
        self.values[key] = narration


def code_block() -> TextBlock:
    return TextBlock(
        page_number=3,
        text="def total(items):\n    return sum(items)",
        bbox=(0, 0, 100, 20),
        font_size=10,
        is_heading=False,
        is_code=True,
    )


def diagram_asset() -> VisualAsset:
    return VisualAsset(
        visual=VisualBlock(page_number=6, bbox=(0, 0, 100, 100), kind="diagram"),
        image_data=b"diagram-png",
        context="Architecture flow",
    )


@pytest.mark.asyncio
async def test_narrator_builds_code_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)

    response = await narrator.narrate_code(
        code_block(), NarrationSettings(code_mode=CodeMode.EXPLAIN)
    )

    assert response.text == "Spoken narration"
    request = adapter.requests[0]
    assert request.metadata["block_type"] == "code"
    assert request.metadata["page_number"] == "3"
    assert request.metadata["language"] == "ru"
    assert request.metadata["code_mode"] == "explain"
    assert request.input_text.startswith("def total")
    assert "Не читай синтаксис посимвольно" in request.instructions


@pytest.mark.asyncio
async def test_narrator_passes_book_usage_context_to_billable_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    context = UsageContext(book_id=uuid4())

    await narrator.narrate_code(code_block(), usage_context=context)

    assert adapter.requests[0].usage_context == context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code_mode", "instruction_fragment"),
    (
        (CodeMode.EXPLAIN, "Объясни фрагмент кода"),
        (CodeMode.READ, "Прочитай фрагмент кода"),
        (CodeMode.HYBRID, "Кратко объясни фрагмент кода"),
    ),
)
async def test_narrator_selects_prompt_for_each_billable_code_mode(
    code_mode: CodeMode, instruction_fragment: str
) -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)

    await narrator.narrate_code(code_block(), NarrationSettings(code_mode=code_mode))

    assert len(adapter.requests) == 1
    assert instruction_fragment in adapter.requests[0].instructions
    assert adapter.requests[0].metadata["code_mode"] == code_mode.value


@pytest.mark.asyncio
async def test_narrator_skips_code_without_a_provider_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)

    response = await narrator.narrate_code(code_block(), NarrationSettings(code_mode=CodeMode.SKIP))

    assert adapter.requests == []
    assert response.model == "code-mode-skip"
    assert response.usage.total_tokens == 0
    assert response.cost.total_cost == 0


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
    assert request.metadata["block_type"] == "table"
    assert request.metadata["page_number"] == "4"
    assert request.metadata["detail"] == "standard"
    assert request.input_text == "Таблица:\nMetric | Value\nPages | 42\nNotes | (пусто)"
    assert "Не придумывай значения" in request.instructions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_mode", "instruction_fragment"),
    (
        (TableMode.SUMMARIZE, "ключевые сравнения"),
        (TableMode.READ_ALL, "все строки со значениями"),
    ),
)
async def test_narrator_selects_prompt_for_each_billable_table_mode(
    table_mode: TableMode, instruction_fragment: str
) -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    table = TableBlock(page_number=4, bbox=(0, 0, 100, 50), cells=(("Metric", "Value"),))

    await narrator.narrate_table(table, NarrationSettings(table_mode=table_mode))

    assert instruction_fragment in adapter.requests[0].instructions
    assert adapter.requests[0].metadata["table_mode"] == table_mode.value


@pytest.mark.asyncio
async def test_narrator_skips_table_without_a_provider_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    table = TableBlock(page_number=4, bbox=(0, 0, 100, 50), cells=(("Metric", "Value"),))

    response = await narrator.narrate_table(table, NarrationSettings(table_mode=TableMode.SKIP))

    assert adapter.requests == []
    assert response.model == "table-mode-skip"
    assert response.cost.total_cost == 0


@pytest.mark.asyncio
async def test_narrator_builds_formula_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    formula = FormulaBlock(page_number=5, text="E = m * c^2", bbox=(0, 0, 100, 20))

    await narrator.narrate_formula(formula)

    request = adapter.requests[0]
    assert request.metadata["block_type"] == "formula"
    assert request.metadata["page_number"] == "5"
    assert request.input_text == "E = m * c^2"
    assert "объясни смысл связи" in request.instructions.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("formula_mode", "instruction_fragment"),
    (
        (FormulaMode.EXPLAIN, "Объясни формулу"),
        (FormulaMode.READ, "Прочитай формулу"),
    ),
)
async def test_narrator_selects_prompt_for_each_billable_formula_mode(
    formula_mode: FormulaMode, instruction_fragment: str
) -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    formula = FormulaBlock(page_number=5, text="E = m * c^2", bbox=(0, 0, 100, 20))

    await narrator.narrate_formula(formula, NarrationSettings(formula_mode=formula_mode))

    assert instruction_fragment in adapter.requests[0].instructions
    assert adapter.requests[0].metadata["formula_mode"] == formula_mode.value


@pytest.mark.asyncio
async def test_narrator_skips_formula_without_a_provider_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    formula = FormulaBlock(page_number=5, text="E = m * c^2", bbox=(0, 0, 100, 20))

    response = await narrator.narrate_formula(
        formula, NarrationSettings(formula_mode=FormulaMode.SKIP)
    )

    assert adapter.requests == []
    assert response.model == "formula-mode-skip"
    assert response.cost.total_cost == 0


@pytest.mark.asyncio
async def test_narrator_reuses_cache_and_invalidates_it_for_new_settings() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter, cache=MemoryNarrationCache())

    first = await narrator.narrate_code(code_block())
    second = await narrator.narrate_code(code_block())
    await narrator.narrate_code(code_block(), NarrationSettings(detail="detailed"))

    assert first.cached is False
    assert second.cached is True
    assert second.text == "Spoken narration"
    assert len(adapter.requests) == 2


@pytest.mark.asyncio
async def test_narrator_builds_vision_request_for_visual_asset() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)
    asset = diagram_asset()

    await narrator.narrate_visual(asset)

    request = adapter.requests[0]
    assert request.metadata["block_type"] == "diagram"
    assert request.metadata["page_number"] == "6"
    assert request.images[0].data == b"diagram-png"
    assert "Architecture flow" in request.input_text
    assert request.metadata["diagram_mode"] == "describe"


@pytest.mark.asyncio
async def test_narrator_skips_diagram_without_a_provider_request() -> None:
    adapter = RecordingAdapter()
    narrator = TechnicalNarrator(adapter)

    response = await narrator.narrate_visual(
        diagram_asset(), NarrationSettings(diagram_mode=DiagramMode.SKIP)
    )

    assert adapter.requests == []
    assert response.model == "diagram-mode-skip"
    assert response.cost.total_cost == 0
