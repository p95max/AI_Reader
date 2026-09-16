from uuid import UUID

from app.models.book import Book, BookStatus
from app.models.user_preferences import UserPreferences
from app.schemas.books import UserPreferencesUpdate
from app.services.books.user_preferences import apply_preferences_to_book


def make_book() -> Book:
    return Book(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        user_id=UUID("87654321-4321-8765-4321-876543218765"),
        title="Technical book",
        author="Author",
        original_filename="book.pdf",
        storage_key="books/book/original.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=BookStatus.UPLOADED,
    )


def test_saved_user_preferences_are_copied_to_the_processing_book() -> None:
    preferences = UserPreferencesUpdate(
        voice="Vivian",
        speed="slow",
        style="expressive",
        code_mode="read",
        table_mode="read_all",
        diagram_mode="skip",
        formula_mode="read",
    )
    book = make_book()

    apply_preferences_to_book(book, preferences)

    assert book.tts_voice == "Vivian"
    assert book.tts_speed == "slow"
    assert book.tts_style == "expressive"
    assert book.code_mode == "read"
    assert book.table_mode == "read_all"
    assert book.diagram_mode == "skip"
    assert book.formula_mode == "read"


def test_orm_preferences_are_copied_to_the_processing_book() -> None:
    preferences = UserPreferences(
        user_id=UUID("87654321-4321-8765-4321-876543218765"),
        voice="Aiden",
        speed="normal",
        style="calm",
        code_mode="hybrid",
        table_mode="summarize",
        diagram_mode="describe",
        formula_mode="explain",
    )
    book = make_book()

    apply_preferences_to_book(book, preferences)

    assert book.tts_voice == "Aiden"
    assert book.code_mode == "hybrid"
    assert book.table_mode == "summarize"
    assert book.diagram_mode == "describe"
    assert book.formula_mode == "explain"
