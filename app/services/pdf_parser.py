import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Protocol

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
        r"(?:\b(?:def|class|return|import|if|else|for|while)\b|[{};]|=>|==|!=)"
    )
    formula_pattern = re.compile(r"[∑∫√≈≤≥±×÷]|\b[A-Za-z]\s*=\s*[^\n.]+[+*/^]")

    def parse_stored_pdf(self, source: PDFSource, storage_key: str) -> ParsedDocument:
        with downloaded_pdf(source, storage_key) as path:
            return self.parse_file(path)

    def parse_file(self, path: Path) -> ParsedDocument:
        try:
            with pymupdf.open(path) as document:
                base_font_size = self._base_font_size(document)
                pages = tuple(
                    self._parse_page(page, page_number, base_font_size)
                    for page_number, page in enumerate(document, start=1)
                )
        except (OSError, RuntimeError, pymupdf.FileDataError) as error:
            raise PDFParsingError(f"Unable to parse PDF: {path.name}") from error

        return ParsedDocument(page_count=len(pages), pages=pages)

    def _base_font_size(self, document: pymupdf.Document) -> float:
        sizes = [
            span["size"]
            for page in document
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]
        return float(median(sizes)) if sizes else 0.0

    def _parse_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        base_font_size: float,
    ) -> ParsedPage:
        blocks: list[TextBlock] = []
        for raw_block in page.get_text("dict", sort=True)["blocks"]:
            if raw_block["type"] != 0:
                continue

            text = "\n".join(
                "".join(span["text"] for span in line["spans"]).strip()
                for line in raw_block["lines"]
            ).strip()
            if not text:
                continue

            spans = [span for line in raw_block["lines"] for span in line["spans"]]
            font_size = max(
                (span["size"] for span in spans),
                default=base_font_size,
            )
            is_heading = base_font_size > 0 and font_size >= base_font_size * self.heading_scale
            uses_monospace_font = any(
                font in span["font"].lower()
                for span in spans
                for font in ("mono", "courier", "consolas", "menlo")
            )
            is_code = not is_heading and (
                uses_monospace_font or bool(self.code_pattern.search(text))
            )
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
            paragraphs=paragraphs,
            headings=headings,
            code_blocks=code_blocks,
            tables=self._extract_tables(page, page_number),
            visuals=self._extract_visuals(page, page_number),
            formulas=formulas,
        )

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
