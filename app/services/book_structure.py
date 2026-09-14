"""Turn parsed PDF headings and blocks into durable book structure."""

from __future__ import annotations

import re
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
    _PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?\d{1,4}\s*$", re.IGNORECASE)

    def build(self, document: ParsedDocument) -> tuple[StructuredChapter, ...]:
        pending: list[_PendingChapter] = []
        current: _PendingChapter | None = None

        for page in document.pages:
            for block in page.text_blocks:
                # PDF extractors commonly emit footer page numbers as independent
                # text blocks. They are not narratable content.
                if self._is_page_number(block.text) or not self._is_usable_text(block.text):
                    continue
                if block.is_heading:
                    explicit_heading = re.match(
                        r"^(?:chapter|part|section|глава|часть|раздел)\s+\S+",
                        block.text.strip(), re.IGNORECASE,
                    )
                    # Cover typography is not a chapter boundary. Preserve all
                    # cover title lines and any intervening content together.
                    if (
                        page.number == 1 and current is not None
                        and current.start_page == 1 and not explicit_heading
                    ):
                        current.title = self._title(f"{current.title} {block.text}")
                        continue
                    # Consecutive headings are typical of a cover page (title,
                    # subtitle, author). Keep only the last candidate until real
                    # content arrives, rather than producing empty chapters.
                    if current is not None and current.blocks:
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

        if current is not None and current.blocks:
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

    @classmethod
    def _is_page_number(cls, text: str) -> bool:
        return bool(cls._PAGE_NUMBER.fullmatch(text))

    @staticmethod
    def _is_usable_text(text: str) -> bool:
        non_whitespace = [character for character in text if not character.isspace()]
        if not non_whitespace:
            return False
        control_count = sum(
            ord(character) < 32 and not character.isspace() for character in non_whitespace
        )
        return control_count / len(non_whitespace) < 0.05
