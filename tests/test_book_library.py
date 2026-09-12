from uuid import UUID

import pytest

from app.models.book import Book, BookStatus
from app.services.book_library import build_book_library_item


def book(status: BookStatus) -> Book:
    return Book(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        title="Python для инженеров",
        author="Unknown author",
        original_filename="python.pdf",
        storage_key="books/book/original.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=status,
    )


def test_library_item_calculates_progress_from_chunk_totals() -> None:
    item = build_book_library_item(book(BookStatus.PROCESSING), total_chunks=4, ready_chunks=3)

    assert item.progress_percent == 75.0
    assert item.author == "Unknown author"


def test_ready_book_without_chunks_is_complete() -> None:
    item = build_book_library_item(book(BookStatus.READY), total_chunks=0, ready_chunks=0)

    assert item.progress_percent == 100.0


def test_invalid_chunk_totals_are_rejected() -> None:
    with pytest.raises(ValueError, match="internally consistent"):
        build_book_library_item(book(BookStatus.PROCESSING), total_chunks=1, ready_chunks=2)
