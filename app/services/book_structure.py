"""Turn parsed PDF headings and blocks into durable book structure."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.pdf_parser import ParsedDocument, TextBlock


@dataclass(frozen=True, slots=True)
class StructuredContentChunk:
    chunk_index: int
    page_number: int
    kind: str
    source_text: str


@dataclass(frozen=True, slots=True)
class StructuredChapter:
    chapter_index: int
    title: str
    start_page: int
    end_page: int
    chunks: tuple[StructuredContentChunk, ...]


@dataclass(slots=True)
class _PendingChapter:
    title: str
    start_page: int
    end_page: int
    blocks: list[TextBlock] = field(default_factory=list)


class BookStructureBuilder:
    """Uses parser-detected headings as chapter boundaries with a safe fallback."""

    fallback_title = "Начало документа"

    def build(self, document: ParsedDocument) -> tuple[StructuredChapter, ...]:
        pending: list[_PendingChapter] = []
        current: _PendingChapter | None = None

        for page in document.pages:
            for block in page.text_blocks:
                if block.is_heading:
                    if current is not None:
                        pending.append(current)
                    current = _PendingChapter(
                        title=self._title(block.text),
                        start_page=page.number,
                        end_page=page.number,
                    )
                    continue
                if current is None:
                    current = _PendingChapter(
                        title=self.fallback_title,
                        start_page=page.number,
                        end_page=page.number,
                    )
                current.end_page = page.number
                current.blocks.append(block)

            if current is not None:
                current.end_page = page.number

        if current is not None:
            pending.append(current)

        return tuple(
            StructuredChapter(
                chapter_index=chapter_index,
                title=chapter.title,
                start_page=chapter.start_page,
                end_page=chapter.end_page,
                chunks=tuple(
                    StructuredContentChunk(
                        chunk_index=chunk_index,
                        page_number=block.page_number,
                        kind="code" if block.is_code else "text",
                        source_text=block.text,
                    )
                    for chunk_index, block in enumerate(chapter.blocks)
                ),
            )
            for chapter_index, chapter in enumerate(pending)
        )

    @staticmethod
    def _title(text: str) -> str:
        return " ".join(text.split())[:500] or BookStructureBuilder.fallback_title
