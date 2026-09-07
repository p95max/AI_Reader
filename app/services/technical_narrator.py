"""Prompt builders that turn parsed technical PDF blocks into spoken narration."""

from app.services.ai_adapter import AIAdapter, AIRequest, AIResponse
from app.services.pdf_parser import FormulaBlock, TableBlock, TextBlock


class TechnicalNarrator:
    """Adapts code, tables and formulas through the shared AI adapter."""

    def __init__(self, adapter: AIAdapter) -> None:
        self._adapter = adapter

    async def narrate_code(self, block: TextBlock) -> AIResponse:
        return await self._adapter.generate(
            AIRequest(
                instructions=(
                    "Объясни фрагмент кода по-русски для прослушивания. Сначала назови его "
                    "назначение, затем кратко опиши ход выполнения, входы, выходы и важные "
                    "ограничения. Не читай синтаксис посимвольно и не добавляй факты, которых "
                    "нет в исходнике."
                ),
                input_text=block.text,
                max_output_tokens=400,
                metadata={"block_type": "code", "page_number": str(block.page_number)},
            )
        )

    async def narrate_table(self, block: TableBlock) -> AIResponse:
        return await self._adapter.generate(
            AIRequest(
                instructions=(
                    "Преобразуй таблицу в компактное русскоязычное narration для прослушивания. "
                    "Назови заголовки, ключевые сравнения и важные числовые значения с единицами. "
                    "Не придумывай значения для пустых ячеек и явно отделяй факты от вывода."
                ),
                input_text=self._format_table(block),
                max_output_tokens=500,
                metadata={"block_type": "table", "page_number": str(block.page_number)},
            )
        )

    async def narrate_formula(self, block: FormulaBlock) -> AIResponse:
        return await self._adapter.generate(
            AIRequest(
                instructions=(
                    "Объясни формулу по-русски для прослушивания. Сначала произнеси её в "
                    "читаемой форме, затем объясни смысл связи и известных переменных. Не "
                    "подставляй отсутствующие значения и не выводи следствия, которых нет "
                    "в формуле."
                ),
                input_text=block.text,
                max_output_tokens=250,
                metadata={"block_type": "formula", "page_number": str(block.page_number)},
            )
        )

    @staticmethod
    def _format_table(block: TableBlock) -> str:
        rows = [" | ".join(cell.strip() or "(пусто)" for cell in row) for row in block.cells]
        return "Таблица:\n" + "\n".join(rows)
