from pathlib import Path

import pymupdf

from app.services.documents.pdf_parser import PDFParser


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


def make_technical_pdf(path: Path) -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Technical chapter", fontsize=20)
        page.insert_text(
            (72, 112),
            "def parse_book(path):\n    return path",
            fontsize=10,
            fontname="cour",
        )
        page.insert_text((72, 152), "E = m * c^2", fontsize=11)

        left, top, cell_width, cell_height = 72, 190, 110, 28
        for row in range(3):
            page.draw_line(
                (left, top + row * cell_height),
                (left + cell_width * 2, top + row * cell_height),
            )
        for column in range(3):
            page.draw_line(
                (left + column * cell_width, top),
                (left + column * cell_width, top + cell_height * 2),
            )
        page.insert_text((80, 210), "Name", fontsize=10)
        page.insert_text((190, 210), "Value", fontsize=10)
        page.insert_text((80, 238), "Pages", fontsize=10)
        page.insert_text((190, 238), "42", fontsize=10)

        pixmap = pymupdf.Pixmap(pymupdf.csRGB, 2, 2, b"\xff\x00\x00" * 4, False)
        page.insert_image(pymupdf.Rect(72, 280, 112, 320), pixmap=pixmap)
        page.draw_rect(pymupdf.Rect(150, 280, 260, 340), color=(0, 0, 0))
        document.save(path)


def make_quality_pdf(path: Path) -> None:
    with pymupdf.open() as document:
        for page_number in range(1, 4):
            page = document.new_page()
            page.insert_text((72, 32), "AI Reader Technical Guide", fontsize=9)
            page.insert_text((72, 810), f"Page {page_number}", fontsize=9)

            if page_number == 2:
                page.insert_text((72, 110), "Left column: first paragraph.", fontsize=11)
                page.insert_text((72, 150), "Left column: second paragraph.", fontsize=11)
                page.insert_text((330, 110), "Right column: first paragraph.", fontsize=11)
                page.insert_text((330, 150), "Right column: second paragraph.", fontsize=11)
            else:
                page.insert_text((72, 110), f"Body content on page {page_number}.", fontsize=11)
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


def test_pdf_parser_detects_technical_blocks(tmp_path: Path) -> None:
    source = tmp_path / "technical.pdf"
    make_technical_pdf(source)

    parsed_page = PDFParser().parse_file(source).pages[0]

    assert parsed_page.code_blocks[0].text.startswith("def parse_book")
    assert parsed_page.tables[0].cells[0] == ("Name", "Value")
    assert {visual.kind for visual in parsed_page.visuals} >= {"image", "diagram"}
    assert parsed_page.formulas[0].text == "E = m * c^2"


def test_pdf_parser_removes_repeated_margins_and_reads_columns(tmp_path: Path) -> None:
    source = tmp_path / "quality.pdf"
    make_quality_pdf(source)

    parsed = PDFParser().parse_file(source)
    two_column_page = parsed.pages[1]

    assert all("AI Reader Technical Guide" not in page.text for page in parsed.pages)
    assert all("Page " not in page.text for page in parsed.pages)
    assert parsed.pages[0].text == "Body content on page 1."
    assert [block.text for block in two_column_page.paragraphs] == [
        "Left column: first paragraph.",
        "Left column: second paragraph.",
        "Right column: first paragraph.",
        "Right column: second paragraph.",
    ]
