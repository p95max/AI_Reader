from uuid import UUID

import pytest

from app.api.v1.routes.books import delete_book
from app.models.book import Book
from app.models.user import User


class FakeSession:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.deleted: list[Book] = []
        self.committed = False

    async def scalar(self, _statement: object) -> Book:
        return self.book

    async def delete(self, book: Book) -> None:
        self.deleted.append(book)

    async def commit(self) -> None:
        self.committed = True


class FakeStorage:
    def __init__(self) -> None:
        self.deleted_prefixes: list[str] = []

    def delete_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)


@pytest.mark.asyncio
async def test_delete_book_removes_entire_storage_prefix_before_database_record() -> None:
    book_id = UUID("12345678-1234-5678-1234-567812345678")
    book = Book(
        id=book_id,
        title="Book",
        author="Author",
        original_filename="book.pdf",
        storage_key="books/book/original.pdf",
        content_type="application/pdf",
        size_bytes=10,
    )
    session = FakeSession(book)
    storage = FakeStorage()

    user = User(id=UUID("87654321-4321-8765-4321-876543218765"), email="reader@example.com")
    response = await delete_book(book_id, session, storage, user)  # type: ignore[arg-type]

    assert response.status_code == 204
    assert storage.deleted_prefixes == [f"books/{book_id}/"]
    assert session.deleted == [book]
    assert session.committed is True
