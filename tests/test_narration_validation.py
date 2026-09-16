import pytest

from app.services.documents.narration_validation import validate_narration
from app.services.documents.pdf_parser import PDFParser


@pytest.mark.parametrize("text", [
    "TRUE!—nervous—very, very dreadfully nervous I had been and am; but why?",
    "If you return for me, I will wait; while the heart beats.",
    "The original story is public domain in most, if not all, countries.",
])
def test_prose_is_not_code(text):
    assert not PDFParser.code_pattern.search(text)


@pytest.mark.parametrize("text", [
    "def parse_book(path):\n    return path",
    "const result = readBook();",
    "for item in books:\n    print(item)",
])
def test_programming_syntax_is_code(text):
    assert PDFParser.code_pattern.search(text)


@pytest.mark.parametrize("text", [
    "Пришлите фрагмент кода.", "Пожалуйста, загрузите PDF.",
    "Please provide the code.", "",
])
def test_assistant_requests_are_rejected(text):
    with pytest.raises(ValueError):
        validate_narration(text)


def test_narrative_is_accepted():
    validate_narration("Правда! Я нервничал, очень, очень сильно нервничал.")
