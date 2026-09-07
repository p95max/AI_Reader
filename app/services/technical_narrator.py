"""Prompt builders that turn parsed technical PDF blocks into spoken narration."""

import hashlib
import json
from dataclasses import asdict, dataclass

from app.services.ai_adapter import (
    AIAdapter,
    AIRequest,
    AIResponse,
    ImageInput,
    TokenUsage,
    UsageCost,
)
from app.services.narration_cache import NarrationCache
from app.services.pdf_parser import FormulaBlock, TableBlock, TextBlock
from app.services.visual_assets import VisualAsset


@dataclass(frozen=True)
class NarrationSettings:
    language: str = "ru"
    detail: str = "standard"
    model: str | None = None


PROMPT_VERSION = "v1"
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
    ) -> AIResponse:
        return await self._narrate(
            block_type="code",
            source=block.text,
            instructions=(
                "Объясни фрагмент кода по-русски для прослушивания. Сначала назови его "
                "назначение, затем кратко опиши ход выполнения, входы, выходы и важные "
                "ограничения. Не читай синтаксис посимвольно и не добавляй факты, которых "
                "нет в исходнике."
            ),
            page_number=block.page_number,
            max_output_tokens=400,
            settings=settings,
        )

    async def narrate_table(
        self,
        block: TableBlock,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
    ) -> AIResponse:
        return await self._narrate(
            block_type="table",
            source=self._format_table(block),
            instructions=(
                "Преобразуй таблицу в компактное русскоязычное narration для прослушивания. "
                "Назови заголовки, ключевые сравнения и важные числовые значения с единицами. "
                "Не придумывай значения для пустых ячеек и явно отделяй факты от вывода."
            ),
            page_number=block.page_number,
            max_output_tokens=500,
            settings=settings,
        )

    async def narrate_formula(
        self,
        block: FormulaBlock,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
    ) -> AIResponse:
        return await self._narrate(
            block_type="formula",
            source=block.text,
            instructions=(
                "Объясни формулу по-русски для прослушивания. Сначала произнеси её в "
                "читаемой форме, затем объясни смысл связи и известных переменных. Не "
                "подставляй отсутствующие значения и не выводи следствия, которых нет "
                "в формуле."
            ),
            page_number=block.page_number,
            max_output_tokens=250,
            settings=settings,
        )

    async def narrate_visual(
        self,
        asset: VisualAsset,
        settings: NarrationSettings = DEFAULT_NARRATION_SETTINGS,
    ) -> AIResponse:
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
                },
                model=settings.model,
                images=images,
            )
        )
        if self._cache is not None:
            await self._cache.set(cache_key, response.text)
        return response

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
