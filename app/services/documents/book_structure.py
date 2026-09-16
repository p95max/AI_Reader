"""Turn parsed PDF headings and blocks into durable book structure."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.documents.pdf_parser import ParsedDocument, ParsedPage, TextBlock


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

    fallback_title = "Start of document"
    # One LLM request per extracted PDF block is unnecessarily expensive and
    # slow. This stays below the narration model's output limit even when an
    # English passage is translated into a more token-dense language.
    max_narration_source_characters = 1_800
    # A title page often looks like a heading to PDF extractors.  When that is
    # the only detected "chapter" in a longer document, keep playback useful
    # by exposing compact, page-based sections rather than one giant item.
    fallback_section_minimum_pages = 4
    fallback_section_page_span = 2
    _PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?\d{1,4}\s*$", re.IGNORECASE)
    _GUTENBERG_START = re.compile(r"\*{3}\s*START OF THE PROJECT GUTENBERG EBOOK", re.I)
    _GUTENBERG_END = re.compile(r"\*{3}\s*END OF THE PROJECT GUTENBERG EBOOK", re.I)
    _NUMBERED_CHAPTER = re.compile(r"^\s*chapter\s+(?:\d+|[ivxlcdm]+)\b", re.IGNORECASE)
    _SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")

    def build(self, document: ParsedDocument) -> tuple[StructuredChapter, ...]:
        pending: list[_PendingChapter] = []
        current: _PendingChapter | None = None

        pages = self._reading_pages(document)
        for page in pages:
            for block in page.text_blocks:
                if page.number == 1 and block.text.strip().casefold() == "by":
                    continue
                # PDF extractors commonly emit footer page numbers as independent
                # text blocks. They are not narratable content.
                if self._is_page_number(block.text) or not self._is_usable_text(block.text):
                    continue
                if block.is_heading:
                    explicit_heading = re.match(
                        r"^(?:chapter|part|section)\s+\S+",
                        block.text.strip(),
                        re.IGNORECASE,
                    )
                    # Cover typography is not a chapter boundary. Preserve all
                    # cover title lines and any intervening content together.
                    if (
                        page.number == 1
                        and current is not None
                        and current.start_page == 1
                        and not explicit_heading
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

        if len(pending) == 1:
            pending = self._split_long_single_section(pending[0])

        return tuple(
            StructuredChapter(
                chapter_index=chapter_index,
                title=chapter.title,
                start_page=chapter.start_page,
                end_page=chapter.end_page,
                chunks=self._narration_chunks(chapter.blocks),
            )
            for chapter_index, chapter in enumerate(pending)
        )

    def _reading_pages(self, document: ParsedDocument) -> tuple[ParsedPage, ...]:
        """Remove Project Gutenberg wrapper material, while retaining ordinary PDFs unchanged."""
        all_blocks = tuple(block for page in document.pages for block in page.text_blocks)
        if not any(self._GUTENBERG_START.search(block.text) for block in all_blocks):
            return document.pages

        pages: list[ParsedPage] = []
        found_start = False
        found_end = False
        for page in document.pages:
            retained: list[TextBlock] = []
            for block in page.text_blocks:
                text = block.text
                if not found_start:
                    start = self._GUTENBERG_START.search(text)
                    if start is None:
                        continue
                    found_start = True
                    text = text[start.end() :]
                if found_end:
                    continue
                end = self._GUTENBERG_END.search(text)
                if end is not None:
                    text = text[: end.start()]
                    found_end = True
                if text.strip():
                    retained.append(
                        TextBlock(
                            page_number=block.page_number,
                            text=text.strip(),
                            bbox=block.bbox,
                            font_size=block.font_size,
                            is_heading=block.is_heading,
                            is_code=block.is_code,
                        )
                    )
            if retained:
                pages.append(
                    ParsedPage(
                        number=page.number,
                        text="\n\n".join(block.text for block in retained),
                        text_blocks=tuple(retained),
                        paragraphs=tuple(
                            block
                            for block in retained
                            if not block.is_heading and not block.is_code
                        ),
                        headings=tuple(block for block in retained if block.is_heading),
                        code_blocks=tuple(block for block in retained if block.is_code),
                        tables=page.tables,
                        visuals=page.visuals,
                        formulas=page.formulas,
                    )
                )

        # Gutenberg PDFs commonly include cover pages and a table of contents
        # before their first numbered chapter. They are navigation metadata,
        # not the audiobook's narrative.
        for page_index, page in enumerate(pages):
            for block_index, block in enumerate(page.text_blocks):
                if not block.is_heading or not self._NUMBERED_CHAPTER.match(block.text):
                    continue
                first_page = ParsedPage(
                    number=page.number,
                    text="\n\n".join(item.text for item in page.text_blocks[block_index:]),
                    text_blocks=page.text_blocks[block_index:],
                    paragraphs=tuple(
                        item
                        for item in page.text_blocks[block_index:]
                        if not item.is_heading and not item.is_code
                    ),
                    headings=tuple(
                        item for item in page.text_blocks[block_index:] if item.is_heading
                    ),
                    code_blocks=tuple(
                        item for item in page.text_blocks[block_index:] if item.is_code
                    ),
                    tables=page.tables,
                    visuals=page.visuals,
                    formulas=page.formulas,
                )
                return (first_page, *pages[page_index + 1 :])
        return tuple(pages)

    def _narration_chunks(self, blocks: list[TextBlock]) -> tuple[StructuredContentChunk, ...]:
        """Batch adjacent prose blocks from one page into cost-efficient AI requests."""
        chunks: list[StructuredContentChunk] = []
        prose: list[str] = []
        prose_page: int | None = None

        def append_chunk(page_number: int, kind: str, text: str) -> None:
            chunks.append(
                StructuredContentChunk(
                    chunk_index=len(chunks),
                    page_number=page_number,
                    kind=kind,
                    source_text=text,
                )
            )

        def flush_prose() -> None:
            nonlocal prose, prose_page
            if prose_page is None or not prose:
                return
            for text in self._split_narration_text("\n\n".join(prose)):
                append_chunk(prose_page, "text", text)
            prose = []
            prose_page = None

        for block in blocks:
            if block.is_code:
                flush_prose()
                for text in self._split_narration_text(block.text):
                    append_chunk(block.page_number, "code", text)
                continue

            combined_length = sum(len(item) for item in prose) + (2 * len(prose)) + len(block.text)
            if prose and (
                block.page_number != prose_page
                or combined_length > self.max_narration_source_characters
            ):
                flush_prose()
            prose_page = block.page_number
            prose.append(block.text)
        flush_prose()
        return tuple(chunks)

    def _split_narration_text(self, text: str) -> tuple[str, ...]:
        """Keep unusually long source blocks within the LLM's reliable output budget."""
        normalized = " ".join(text.split())
        if len(normalized) <= self.max_narration_source_characters:
            return (normalized,) if normalized else ()

        chunks: list[str] = []
        current = ""
        for sentence in self._SENTENCE_BOUNDARY.split(normalized):
            while len(sentence) > self.max_narration_source_characters:
                split_at = sentence.rfind(" ", 0, self.max_narration_source_characters + 1)
                if split_at <= 0:
                    split_at = self.max_narration_source_characters
                part, sentence = sentence[:split_at].strip(), sentence[split_at:].strip()
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(part)
            if not current:
                current = sentence
            elif len(current) + len(sentence) + 1 <= self.max_narration_source_characters:
                current = f"{current} {sentence}"
            else:
                chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)
        return tuple(chunks)

    def _split_long_single_section(self, chapter: _PendingChapter) -> list[_PendingChapter]:
        page_count = chapter.end_page - chapter.start_page + 1
        if page_count < self.fallback_section_minimum_pages:
            return [chapter]

        sections: list[_PendingChapter] = []
        start_page = chapter.start_page
        end_page = min(
            start_page + self.fallback_section_page_span - 1,
            chapter.end_page,
        )
        blocks: list[TextBlock] = []

        for block in chapter.blocks:
            while block.page_number > end_page:
                if blocks:
                    sections.append(
                        _PendingChapter(
                            title=f"Section {len(sections) + 1}",
                            start_page=start_page,
                            end_page=end_page,
                            blocks=blocks,
                        )
                    )
                start_page = end_page + 1
                end_page = min(
                    start_page + self.fallback_section_page_span - 1,
                    chapter.end_page,
                )
                blocks = []
            blocks.append(block)

        if blocks:
            sections.append(
                _PendingChapter(
                    title=f"Section {len(sections) + 1}",
                    start_page=start_page,
                    end_page=chapter.end_page,
                    blocks=blocks,
                )
            )
        return sections or [chapter]

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
