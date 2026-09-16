from app.services.books.book_metadata import UNKNOWN_AUTHOR, resolve_book_metadata


def test_metadata_author_takes_priority_over_cover_text() -> None:
    result = resolve_book_metadata(
        {"title": "The Tell-Tale Heart", "author": "Edgar Allan Poe"},
        "THE TELL-TALE HEART\nANOTHER PERSON",
        "Tell-Tale_Heart.pdf",
    )

    assert result.title == "The Tell-Tale Heart"
    assert result.author == "Edgar Allan Poe"


def test_cover_title_followed_by_uppercase_author_is_detected() -> None:
    result = resolve_book_metadata(
        {},
        "THE TELL-TALE HEART EDGAR ALLAN POE\nA short story",
        "Tell-Tale_Heart.pdf",
    )

    assert result.title == "Tell-Tale Heart"
    assert result.author == "Edgar Allan Poe"


def test_metadata_extraction_keeps_unknown_author_when_no_evidence_exists() -> None:
    result = resolve_book_metadata({}, "A document without a title page", "notes.pdf")

    assert result.title == "notes"
    assert result.author == UNKNOWN_AUTHOR


def test_cover_copyright_year_is_used_but_pdf_creation_date_is_not() -> None:
    result = resolve_book_metadata(
        {"creationDate": "D:20260914080000", "subject": "Published in 1843"},
        "THE TELL-TALE HEART\nEDGAR ALLAN POE",
        "Tell-Tale_Heart.pdf",
    )

    assert result.publication_year == 1843
