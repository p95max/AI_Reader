"""Read model backing the library screen."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.book import Book, BookStatus


@dataclass(frozen=True, slots=True)
class BookLibraryItem:
    id: UUID
    title: str
    author: str
    publication_year: int | None
    status: BookStatus
    progress_percent: float


def build_book_library_item(book: Book, *, total_chunks: int, ready_chunks: int) -> BookLibraryItem:
    """Create a card-ready summary without loading all individual chunks."""
    if total_chunks < 0 or ready_chunks < 0 or ready_chunks > total_chunks:
        raise ValueError("chunk totals must be non-negative and internally consistent")
    if total_chunks:
        progress_percent = round(ready_chunks / total_chunks * 100, 2)
    else:
        progress_percent = 100.0 if book.status == BookStatus.READY else 0.0
    return BookLibraryItem(
        id=book.id,
        title=book.title,
        author=book.author,
        publication_year=book.publication_year,
        status=book.status,
        progress_percent=progress_percent,
    )
