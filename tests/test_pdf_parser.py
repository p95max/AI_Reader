from pathlib import Path

import pymupdf

from app.services.pdf_parser import PDFParser


class LocalPDFSource:
    def __init__(self, source: Path) -> None:
        self.source = source

    def download_file(self, key: str, destination: Path) -> None:
        destination.write_bytes(self.source.read_bytes())


def make_pdf(path: Path) -> None:
    with pymupdf.open() as document:
        first_page = document.new_page()
        first_page.insert_text((72, 72), "Chapter One", fontsize=20)
        first_page.insert_text(
            (72, 112),
            "The first paragraph explains the chapter.\nIt continues on a second line.",
            fontsize=11,
        )
        second_page = document.new_page()
        second_page.insert_text((72, 72), "Second page paragraph.", fontsize=11)
        document.save(path)


def test_pdf_parser_extracts_pages_paragraphs_and_headings(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    make_pdf(source)

    parsed = PDFParser().parse_file(source)

    assert parsed.page_count == 2
    assert parsed.pages[0].headings[0].text == "Chapter One"
    assert "first paragraph" in parsed.pages[0].paragraphs[0].text
    assert parsed.pages[1].text == "Second page paragraph."


def test_pdf_parser_downloads_from_storage_and_removes_temporary_file(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    make_pdf(source)

    parsed = PDFParser().parse_stored_pdf(LocalPDFSource(source), "books/example/original.pdf")

    assert parsed.page_count == 2
