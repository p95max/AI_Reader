"""Prompt builders that turn parsed technical PDF blocks into spoken narration."""

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from app.core.reading_language import narration_language_instruction
from app.services.ai.ai_adapter import (
    AIAdapter,
    AIRequest,
    AIResponse,
    ImageInput,
    TokenUsage,
    UsageContext,
    UsageCost,
)
from app.services.ai.narration_cache import NarrationCache
from app.services.ai.visual_assets import VisualAsset
from app.services.documents.pdf_parser import FormulaBlock, TableBlock, TextBlock


class CodeMode(StrEnum):
    EXPLAIN = "explain"
    READ = "read"
    SKIP = "skip"
    HYBRID = "hybrid"


class TableMode(StrEnum):
    SUMMARIZE = "summarize"
    READ_ALL = "read_all"
    SKIP = "skip"


class DiagramMode(StrEnum):
    DESCRIBE = "describe"
    SKIP = "skip"


class FormulaMode(StrEnum):
    EXPLAIN = "explain"
    READ = "read"
    SKIP = "skip"


@dataclass(frozen=True)
class NarrationSettings:
    language: str = "auto"
    detail: str = "standard"
    model: str | None = None
    code_mode: CodeMode = CodeMode.HYBRID
    table_mode: TableMode = TableMode.SUMMARIZE
    diagram_mode: DiagramMode = DiagramMode.DESCRIBE
    formula_mode: FormulaMode = FormulaMode.EXPLAIN


PROMPT_VERSION = "v3"
DEFAULT_NARRATION_SETTINGS = NarrationSettings()


class TechnicalNarrator:
    """Adapts code, tables and formulas through the shared AI adapter."""

    def __init__(self, adapter: AIAdapter, cache: NarrationCache | None = None) -> None:
        self._adapter = adapter
        self._cache = cache

    async def narrate_code(
        self,
        block: TextBlock,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
        usage_context: UsageContext | None = None,
    ) -> AIResponse:
        if settings.code_mode == CodeMode.SKIP:
            return self._skipped("code", settings.language)
        instructions = {
            CodeMode.EXPLAIN: (
                "Explain this code fragment for listening. First state its purpose, then briefly "
                "describe its execution flow, inputs, outputs, and important constraints. Do not "
                "read syntax character by character or add facts not present in the source."
            ),
            CodeMode.READ: (
                "Read this code fragment as closely as possible to the source, converting syntax "
                "into clear spoken form. Read symbol names, indentation, brackets, and operators "
                "in sequence. Do not explain the code's meaning."
            ),
            CodeMode.HYBRID: (
                "Briefly explain this code fragment for listening: state its purpose and key "
                "logic, then read only important names, calls, and constraints. Do not "
                "reproduce it character by character or add facts beyond the source."
            ),
        }[settings.code_mode]
        return await self._narrate(
            block_type="code",
            source=block.text,
            instructions=instructions,
            page_number=block.page_number,
            max_output_tokens=400,
            settings=settings,
            usage_context=usage_context,
        )

    async def narrate_table(
        self,
        block: TableBlock,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
        usage_context: UsageContext | None = None,
    ) -> AIResponse:
        if settings.table_mode == TableMode.SKIP:
            return self._skipped("table", settings.language)
        instructions = {
            TableMode.SUMMARIZE: (
                "Turn this table into compact narration for listening. State the headers, key "
                "comparisons, and important numerical values with units. Do not invent values for "
                "empty cells and clearly distinguish facts from conclusions."
            ),
            TableMode.READ_ALL: (
                "Read this table in full for listening. State every column header and every row "
                "with values, including units. Mark empty cells as empty; do not summarise or omit "
                "anything."
            ),
        }[settings.table_mode]
        return await self._narrate(
            block_type="table",
            source=self._format_table(block),
            instructions=instructions,
            page_number=block.page_number,
            max_output_tokens=800 if settings.table_mode == TableMode.READ_ALL else 500,
            settings=settings,
            usage_context=usage_context,
        )

    async def narrate_formula(
        self,
        block: FormulaBlock,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
        usage_context: UsageContext | None = None,
    ) -> AIResponse:
        if settings.formula_mode == FormulaMode.SKIP:
            return self._skipped("formula", settings.language)
        instructions = {
            FormulaMode.EXPLAIN: (
                "Explain this formula for listening. First say it in readable form, then explain "
                "the relationship and known variables. Do not substitute missing values or infer "
                "conclusions not present in the formula."
            ),
            FormulaMode.READ: (
                "Read this formula in clear spoken form, saying variables, subscripts, exponents, "
                "operators, and brackets in sequence. Do not explain its meaning or add missing "
                "values."
            ),
        }[settings.formula_mode]
        return await self._narrate(
            block_type="formula",
            source=block.text,
            instructions=instructions,
            page_number=block.page_number,
            max_output_tokens=250,
            settings=settings,
            usage_context=usage_context,
        )

    async def narrate_visual(
        self,
        asset: VisualAsset,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
        usage_context: UsageContext | None = None,
    ) -> AIResponse:
        if settings.diagram_mode == DiagramMode.SKIP:
            return self._skipped("diagram", settings.language)
        visual_kind = "diagram" if asset.visual.kind == "diagram" else "image"
        source = hashlib.sha256(asset.image_data).hexdigest()
        return await self._narrate(
            block_type=asset.visual.kind,
            source=f"{source}\n{asset.context}",
            instructions=(
                f"Describe this {visual_kind} for listening. First name its type and main idea, "
                "then briefly explain its elements and connections. Do not invent unreadable "
                "labels or details."
            ),
            input_text=(
                f"Analyse the {visual_kind} on page {asset.visual.page_number}.\n"
                f"Context: {asset.context or '(no surrounding text)'}"
            ),
            page_number=asset.visual.page_number,
            max_output_tokens=400,
            settings=settings,
            images=(ImageInput(data=asset.image_data, media_type=asset.media_type),),
            usage_context=usage_context,
        )

    async def _narrate(
        self,
        *,
        block_type: str,
        source: str,
        instructions: str,
        page_number: int,
        max_output_tokens: int,
        settings: NarrationSettings,
        input_text: str | None = None,
        images: tuple[ImageInput, ...] = (),
        usage_context: UsageContext | None = None,
    ) -> AIResponse:
        cache_key = self._cache_key(block_type, source, instructions, settings)
        if self._cache is not None:
            cached_text = await self._cache.get(cache_key)
            if cached_text is not None:
                return AIResponse(
                    text=cached_text,
                    model="narration-cache",
                    usage=TokenUsage(),
                    cost=UsageCost(input_cost=0, cached_input_cost=0, output_cost=0),
                    provider_response_id=None,
                    cached=True,
                )

        response = await self._adapter.generate(
            AIRequest(
                instructions=(
                    f"{narration_language_instruction(settings.language)} "
                    f"{instructions} Return only spoken narration."
                ),
                input_text=input_text or source,
                max_output_tokens=max_output_tokens,
                metadata={
                    "block_type": block_type,
                    "page_number": str(page_number),
                    "language": settings.language,
                    "detail": settings.detail,
                    "code_mode": settings.code_mode.value,
                    "table_mode": settings.table_mode.value,
                    "diagram_mode": settings.diagram_mode.value,
                    "formula_mode": settings.formula_mode.value,
                },
                model=settings.model,
                images=images,
                usage_context=usage_context,
            )
        )
        if self._cache is not None:
            await self._cache.set(cache_key, response.text)
        return response

    @staticmethod
    def _skipped(block_type: str, language: str) -> AIResponse:
        messages_by_language = {
            "en": {
                "code": "Code fragment skipped by the reading setting.",
                "table": "Table skipped by the reading setting.",
                "diagram": "Diagram skipped by the reading setting.",
                "formula": "Formula skipped by the reading setting.",
            },
            "de": {
                "code": "Codeabschnitt wurde durch die Leseeinstellung übersprungen.",
                "table": "Tabelle wurde durch die Leseeinstellung übersprungen.",
                "diagram": "Diagramm wurde durch die Leseeinstellung übersprungen.",
                "formula": "Formel wurde durch die Leseeinstellung übersprungen.",
            },
        }
        messages = messages_by_language.get(language, messages_by_language["en"])
        return AIResponse(
            text=messages[block_type],
            model=f"{block_type}-mode-skip",
            usage=TokenUsage(),
            cost=UsageCost(input_cost=0, cached_input_cost=0, output_cost=0),
            provider_response_id=None,
            cached=False,
        )

    @staticmethod
    def _cache_key(
        block_type: str,
        source: str,
        instructions: str,
        settings: NarrationSettings,
    ) -> str:
        payload = json.dumps(
            {
                "block_type": block_type,
                "source": source,
                "instructions": instructions,
                "prompt_version": PROMPT_VERSION,
                "settings": asdict(settings),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "ai-reader:narration:" + hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _format_table(block: TableBlock) -> str:
        rows = [" | ".join(cell.strip() or "(empty)" for cell in row) for row in block.cells]
        return "Table:\n" + "\n".join(rows)
