import pytest
from pydantic import ValidationError

from app.core.reading_language import (
    ReadingLanguage,
    narration_language_instruction,
    preserves_source_language,
)
from app.schemas.books import BookTTSSettingsUpdate


def test_auto_detect_keeps_the_source_language() -> None:
    instruction = narration_language_instruction(ReadingLanguage.AUTO)

    assert "same language" in instruction
    assert "Do not translate" in instruction
    assert preserves_source_language(ReadingLanguage.AUTO)


@pytest.mark.parametrize(
    ("language", "name"),
    (("en", "English"), ("de", "German")),
)
def test_explicit_language_requests_translation_when_needed(language: str, name: str) -> None:
    assert name in narration_language_instruction(language)
    assert not preserves_source_language(language)


def test_processing_preferences_validate_the_supported_reading_languages() -> None:
    assert BookTTSSettingsUpdate(reading_language="de").reading_language is ReadingLanguage.GERMAN

    with pytest.raises(ValidationError):
        BookTTSSettingsUpdate(reading_language="fr")
