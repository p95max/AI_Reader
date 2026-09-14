import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from statistics import median
from typing import Any, Protocol

import pymupdf


class PDFParsingError(RuntimeError):
    """Raised when a PDF cannot be opened or parsed."""


class PDFSource(Protocol):
    def download_file(self, key: str, destination: Path) -> None: ...


@dataclass(frozen=True)
class TextBlock:
    page_number: int
    text: str
    bbox: tuple[float, float, float, float]
    font_size: float
    is_heading: bool
    is_code: bool


@dataclass(frozen=True)
class TableBlock:
    page_number: int
    bbox: tuple[float, float, float, float]
    cells: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class VisualBlock:
    page_number: int
    bbox: tuple[float, float, float, float]
    kind: str


@dataclass(frozen=True)
class FormulaBlock:
    page_number: int
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ParsedPage:
    number: int
    text: str
    text_blocks: tuple[TextBlock, ...]
    paragraphs: tuple[TextBlock, ...]
    headings: tuple[TextBlock, ...]
    code_blocks: tuple[TextBlock, ...]
    tables: tuple[TableBlock, ...]
    visuals: tuple[VisualBlock, ...]
    formulas: tuple[FormulaBlock, ...]


@dataclass(frozen=True)
class ParsedDocument:
    page_count: int
    pages: tuple[ParsedPage, ...]


@contextmanager
def downloaded_pdf(source: PDFSource, storage_key: str) -> Iterator[Path]:
    """Download a stored PDF to a temporary file and remove it afterwards."""
    descriptor, raw_path = tempfile.mkstemp(suffix=".pdf")
    os.close(descriptor)
    path = Path(raw_path)

    try:
        source.download_file(storage_key, path)
        yield path
    finally:
        path.unlink(missing_ok=True)


class PDFParser:
    """Extract baseline reading structure from text-layer PDFs with PyMuPDF."""

    heading_scale = 1.2
    code_pattern = re.compile(
        r"^\s*(?:"
        r"(?:async\s+)?def\s+\w+\s*\([^\n]*\)\s*:"
        r"|class\s+\w+(?:\([^\n]*\))?\s*:"
        r"|from\s+[\w.]+\s+import\s+\w+"
        r"|import\s+[\w.]+\s*$"
        r"|(?:const|let|var)\s+\w+\s*="
        r"|(?:if|for|while)\s*\([^\n]*\)\s*\{"
        r"|(?:if|for|while)\s+[^\n]+:\s*$"
        r"|(?:public|private|static)\s+(?:static\s+)?\w+\s+\w+\s*\("
        r")", re.MULTILINE,
    )
    formula_pattern = re.compile(r"[∑∫√≈≤≥±×÷]|\b[A-Za-z]\s*=\s*[^\n.]+[+*/^]")

    def parse_stored_pdf(self, source: PDFSource, storage_key: str) -> ParsedDocument:
        with downloaded_pdf(source, storage_key) as path:
            return self.parse_file(path)

    def parse_file(self, path: Path) -> ParsedDocument:
        try:
            with pymupdf.open(path) as document:
                repeated_margins = self._repeated_margin_text(document)
                base_font_size = self._base_font_size(document, repeated_margins)
                pages = tuple(
                    self._parse_page(page, page_number, base_font_size, repeated_margins)
                    for page_number, page in enumerate(document, start=1)
                )
        except (OSError, RuntimeError, pymupdf.FileDataError) as error:
            raise PDFParsingError(f"Unable to parse PDF: {path.name}") from error

        return ParsedDocument(page_count=len(pages), pages=pages)

    def _base_font_size(
        self,
        document: pymupdf.Document,
        repeated_margins: frozenset[str],
    ) -> float:
        sizes = [
            span["size"]
            for page in document
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            if self._normalized_margin_text(self._text_from_block(block)) not in repeated_margins
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]
        return float(median(sizes)) if sizes else 0.0

    def _repeated_margin_text(self, document: pymupdf.Document) -> frozenset[str]:
        occurrences: dict[str, set[int]] = {}
        for page_number, page in enumerate(document, start=1):
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0 or not self._is_margin_block(block, page):
                    continue
                normalized = self._normalized_margin_text(self._text_from_block(block))
                if normalized:
                    occurrences.setdefault(normalized, set()).add(page_number)

        minimum_pages = max(2, ceil(len(document) / 2))
        return frozenset(text for text, pages in occurrences.items() if len(pages) >= minimum_pages)

    def _parse_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        base_font_size: float,
        repeated_margins: frozenset[str],
    ) -> ParsedPage:
        blocks: list[TextBlock] = []
        raw_blocks = self._ordered_text_blocks(page, repeated_margins)
        for raw_block, text in raw_blocks:
            spans = [span for line in raw_block["lines"] for span in line["spans"]]
            font_size = max(
                (span["size"] for span in spans),
                default=base_font_size,
            )
            is_heading = base_font_size > 0 and font_size >= base_font_size * self.heading_scale
            # A monospaced font is common in scanned/test PDFs and is not enough
            # evidence on its own. Require recognizable programming syntax before
            # routing a block to the code-narration path.
            has_code_syntax = bool(self.code_pattern.search(text))
            is_code = not is_heading and has_code_syntax
            blocks.append(
                TextBlock(
                    page_number=page_number,
                    text=text,
                    bbox=tuple(raw_block["bbox"]),
                    font_size=font_size,
                    is_heading=is_heading,
                    is_code=is_code,
                )
            )

        headings = tuple(block for block in blocks if block.is_heading)
        code_blocks = tuple(block for block in blocks if block.is_code)
        paragraphs = tuple(block for block in blocks if not block.is_heading and not block.is_code)
        formulas = tuple(
            FormulaBlock(page_number=page_number, text=block.text, bbox=block.bbox)
            for block in paragraphs
            if self.formula_pattern.search(block.text)
        )
        return ParsedPage(
            number=page_number,
            text="\n\n".join(block.text for block in blocks),
            text_blocks=tuple(blocks),
            paragraphs=paragraphs,
            headings=headings,
            code_blocks=code_blocks,
            tables=self._extract_tables(page, page_number),
            visuals=self._extract_visuals(page, page_number),
            formulas=formulas,
        )

    def _ordered_text_blocks(
        self,
        page: pymupdf.Page,
        repeated_margins: frozenset[str],
    ) -> list[tuple[dict[str, Any], str]]:
        blocks = [
            (block, text)
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            if (text := self._text_from_block(block))
            if self._normalized_margin_text(text) not in repeated_margins
        ]
        if len(blocks) < 4:
            return sorted(blocks, key=self._vertical_position)

        x_positions = sorted({block["bbox"][0] for block, _ in blocks})
        gaps = [
            (right - left, (left + right) / 2)
            for left, right in zip(x_positions, x_positions[1:], strict=False)
        ]
        if not gaps:
            return sorted(blocks, key=self._vertical_position)

        largest_gap, split_x = max(gaps)
        if largest_gap < page.rect.width * 0.2:
            return sorted(blocks, key=self._vertical_position)

        left_column = [block for block in blocks if block[0]["bbox"][0] < split_x]
        right_column = [block for block in blocks if block[0]["bbox"][0] >= split_x]
        if min(len(left_column), len(right_column)) < 2:
            return sorted(blocks, key=self._vertical_position)

        return sorted(left_column, key=self._vertical_position) + sorted(
            right_column,
            key=self._vertical_position,
        )

    @staticmethod
    def _text_from_block(block: dict[str, Any]) -> str:
        return "\n".join(
            "".join(span["text"] for span in line["spans"]).strip() for line in block["lines"]
        ).strip()

    @staticmethod
    def _normalized_text(text: str) -> str:
        return " ".join(text.casefold().split())

    @classmethod
    def _normalized_margin_text(cls, text: str) -> str:
        normalized = cls._normalized_text(text)
        if re.fullmatch(r"(?:page|p\.?|страница)\s+\d+", normalized):
            return re.sub(r"\d+", "#", normalized)
        return normalized

    @staticmethod
    def _vertical_position(block: tuple[dict[str, Any], str]) -> tuple[float, float]:
        bbox = block[0]["bbox"]
        return bbox[1], bbox[0]

    @staticmethod
    def _is_margin_block(block: dict[str, Any], page: pymupdf.Page) -> bool:
        top = block["bbox"][1]
        bottom = block["bbox"][3]
        margin_height = page.rect.height * 0.15
        return top <= margin_height or bottom >= page.rect.height - margin_height

    def _extract_tables(self, page: pymupdf.Page, page_number: int) -> tuple[TableBlock, ...]:
        try:
            table_finder = page.find_tables()
        except RuntimeError, ValueError:
            return ()

        return tuple(
            TableBlock(
                page_number=page_number,
                bbox=tuple(table.bbox),
                cells=tuple(tuple(cell or "" for cell in row) for row in table.extract()),
            )
            for table in table_finder.tables
        )

    def _extract_visuals(self, page: pymupdf.Page, page_number: int) -> tuple[VisualBlock, ...]:
        visuals: list[VisualBlock] = []
        for image in page.get_images(full=True):
            for rect in page.get_image_rects(image[0]):
                visuals.append(
                    VisualBlock(
                        page_number=page_number,
                        bbox=tuple(rect),
                        kind="image",
                    )
                )

        for drawing in page.get_drawings():
            rect = drawing["rect"]
            if rect.get_area() > 0:
                visuals.append(
                    VisualBlock(
                        page_number=page_number,
                        bbox=tuple(rect),
                        kind="diagram",
                    )
                )
        return tuple(visuals)
