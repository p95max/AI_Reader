"""Language policy for generated audiobook narration."""

from enum import StrEnum


class ReadingLanguage(StrEnum):
    """Supported target languages for a book's generated narration."""

    AUTO = "auto"
    ENGLISH = "en"
    RUSSIAN = "ru"
    GERMAN = "de"


def narration_language_instruction(language: ReadingLanguage | str) -> str:
    """Return an unambiguous output-language instruction for an AI request."""
    selected = ReadingLanguage(language)
    if selected is ReadingLanguage.AUTO:
        return (
            "Detect the passage's primary natural language and produce the narration in that "
            "same language. Do not translate it."
        )

    language_name = {
        ReadingLanguage.ENGLISH: "English",
        ReadingLanguage.RUSSIAN: "Russian",
        ReadingLanguage.GERMAN: "German",
    }[selected]
    return f"Produce the narration in {language_name}, translating the source when necessary."


def preserves_source_language(language: ReadingLanguage | str) -> bool:
    """Whether ordinary prose can bypass the LLM and go straight to TTS."""
    return ReadingLanguage(language) is ReadingLanguage.AUTO
