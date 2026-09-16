from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.book import Book
from app.services.books.book_cost import BookCostService


class FakeResult:
    def __init__(self, row: tuple[object, ...]) -> None:
        self._row = row

    def one(self) -> tuple[object, ...]:
        return self._row


class FakeSession:
    def __init__(self, book: Book) -> None:
        self._book = book
        self._rows = [
            (Decimal("1.20"), 100, 20, 30, 2),
            (Decimal("2.30"), 3_000, 2_000),
        ]

    async def get(self, _model: type[Book], _book_id: object) -> Book:
        return self._book

    async def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self._rows.pop(0))


@pytest.mark.asyncio
async def test_book_cost_combines_llm_and_tts_actual_cost() -> None:
    book = Book(
        id=uuid4(),
        user_id=uuid4(),
        title="Costed book",
        original_filename="costed.pdf",
        storage_key="books/costed/original.pdf",
        content_type="application/pdf",
        size_bytes=10,
        estimated_ai_cost_usd=0.5,
        estimate_model_name="gpt-costed",
        estimate_pricing_version="2026-09",
    )
    comparison = await BookCostService(FakeSession(book)).get(book.id)  # type: ignore[arg-type]

    assert comparison.actual_cost_usd == pytest.approx(1.2)
    assert comparison.actual_tts_cost_usd == pytest.approx(2.3)
    assert comparison.generated_audio_seconds == 3
    assert comparison.tts_generation_seconds == 2
    assert comparison.total_processing_cost_usd == pytest.approx(3.5)
