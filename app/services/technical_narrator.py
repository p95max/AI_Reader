"""Prompt builders that turn parsed technical PDF blocks into spoken narration."""

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from app.services.ai_adapter import (
    AIAdapter,
    AIRequest,
    AIResponse,
    ImageInput,
    TokenUsage,
    UsageContext,
    UsageCost,
)
from app.services.narration_cache import NarrationCache
from app.services.pdf_parser import FormulaBlock, TableBlock, TextBlock
from app.services.visual_assets import VisualAsset


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
    language: str = "ru"
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
            return self._skipped("code")
        instructions = {
            CodeMode.EXPLAIN: (
                "Объясни фрагмент кода по-русски для прослушивания. Сначала назови его "
                "назначение, затем кратко опиши ход выполнения, входы, выходы и важные "
                "ограничения. Не читай синтаксис посимвольно и не добавляй факты, которых "
                "нет в исходнике."
            ),
            CodeMode.READ: (
                "Прочитай фрагмент кода по-русски максимально близко к исходнику, но "
                "преобразуй синтаксис в понятную устную форму: названия символов, отступы, "
                "скобки и операторы произноси последовательно. Не объясняй смысл кода."
            ),
            CodeMode.HYBRID: (
                "Кратко объясни фрагмент кода по-русски для прослушивания: назови назначение "
                "и ключевую логику, затем прочитай только важные имена, вызовы и ограничения. "
                "Не воспроизводи код посимвольно и не добавляй факты вне исходника."
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
            return self._skipped("table")
        instructions = {
            TableMode.SUMMARIZE: (
                "Преобразуй таблицу в компактное русскоязычное narration для прослушивания. "
                "Назови заголовки, ключевые сравнения и важные числовые значения с единицами. "
                "Не придумывай значения для пустых ячеек и явно отделяй факты от вывода."
            ),
            TableMode.READ_ALL: (
                "Прочитай таблицу по-русски целиком для прослушивания. Последовательно назови "
                "заголовки всех столбцов и все строки со значениями, включая единицы измерения. "
                "Пустые ячейки обозначай как пустые, ничего не суммируй и не пропускай."
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
            return self._skipped("formula")
        instructions = {
            FormulaMode.EXPLAIN: (
                "Объясни формулу по-русски для прослушивания. Сначала произнеси её в "
                "читаемой форме, затем объясни смысл связи и известных переменных. Не "
                "подставляй отсутствующие значения и не выводи следствия, которых нет "
                "в формуле."
            ),
            FormulaMode.READ: (
                "Прочитай формулу по-русски в понятной устной форме, последовательно "
                "произнося переменные, индексы, степени, знаки операций и скобки. Не "
                "объясняй смысл формулы и не добавляй отсутствующие значения."
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
            return self._skipped("diagram")
        visual_kind = "схема" if asset.visual.kind == "diagram" else "изображение"
        source = hashlib.sha256(asset.image_data).hexdigest()
        return await self._narrate(
            block_type=asset.visual.kind,
            source=f"{source}\n{asset.context}",
            instructions=(
                f"Опиши {visual_kind} по-русски для прослушивания. Сначала назови её тип и "
                "главную идею, затем кратко объясни элементы и связи между ними. Не выдумывай "
                "неразборчивые подписи или детали."
            ),
            input_text=(
                f"Проанализируй {visual_kind} на странице {asset.visual.page_number}.\n"
                f"Контекст: {asset.context or '(нет текста вокруг изображения)'}"
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
                instructions=instructions,
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
    def _skipped(block_type: str) -> AIResponse:
        messages = {
            "code": "Фрагмент кода пропущен по настройке чтения.",
            "table": "Таблица пропущена по настройке чтения.",
            "diagram": "Диаграмма пропущена по настройке чтения.",
            "formula": "Формула пропущена по настройке чтения.",
        }
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
        rows = [" | ".join(cell.strip() or "(пусто)" for cell in row) for row in block.cells]
        return "Таблица:\n" + "\n".join(rows)
