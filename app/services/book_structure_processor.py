"""Application service for creating a book's derived reading structure."""

from __future__ import annotations

from uuid import UUID

from app.services.book_structure import BookStructureBuilder, StructuredChapter
from app.services.book_structure_store import BookStructureStore
from app.services.pdf_parser import ParsedDocument


class BookStructureProcessor:
    def __init__(self, builder: BookStructureBuilder, store: BookStructureStore) -> None:
        self._builder = builder
        self._store = store

    async def create(
        self, book_id: UUID, document: ParsedDocument
    ) -> tuple[StructuredChapter, ...]:
        chapters = self._builder.build(document)
        await self._store.replace(book_id, chapters)
        return chapters
