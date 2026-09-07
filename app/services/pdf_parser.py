import os
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


@dataclass(frozen=True)
class ParsedPage:
    number: int
    text: str
    paragraphs: tuple[TextBlock, ...]
    headings: tuple[TextBlock, ...]


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

            font_size = max(
                (span["size"] for line in raw_block["lines"] for span in line["spans"]),
                default=base_font_size,
            )
            is_heading = base_font_size > 0 and font_size >= base_font_size * self.heading_scale
            blocks.append(
                TextBlock(
                    page_number=page_number,
                    text=text,
                    bbox=tuple(raw_block["bbox"]),
                    font_size=font_size,
                    is_heading=is_heading,
                )
            )

        headings = tuple(block for block in blocks if block.is_heading)
        paragraphs = tuple(block for block in blocks if not block.is_heading)
        return ParsedPage(
            number=page_number,
            text="\n\n".join(block.text for block in blocks),
            paragraphs=paragraphs,
            headings=headings,
        )
