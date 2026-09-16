"""Reject assistant replies that cannot serve as audiobook narration."""

import re

_REQUEST_FOR_SOURCE = re.compile(
    r"(?:please\s+)?(?:upload|provide|paste|send)\s+(?:the\s+|a\s+|your\s+)?"
    r"(?:pdf|code|source text|text passage)",
    re.IGNORECASE,
)


def validate_narration(text: str) -> None:
    if not text.strip() or _REQUEST_FOR_SOURCE.search(text):
        raise ValueError("Narration is empty or requests source material instead of reading it")
