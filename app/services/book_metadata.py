"""Best-effort, local extraction of a PDF's display title and author."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pymupdf


UNKNOWN_AUTHOR = "Unknown author"
_AUTHOR_LABEL = re.compile(
    r"(?:^|\n)\s*(?:by|written by|author)\s*[:\-]?\s*([^\n]{3,100})",
    re.IGNORECASE,
)
_UPPERCASE_NAME = re.compile(r"\b([A-Z][A-Z.'-]*(?:\s+[A-Z][A-Z.'-]*){1,5})\b")
_TITLECASE_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,5})\b")
_NOT_A_NAME = frozenset({"CHAPTER", "CONTENTS", "COPYRIGHT", "PUBLISHED", "ALL RIGHTS", "PAGE"})


@dataclass(frozen=True, slots=True)
class ExtractedBookMetadata:
    title: str
    author: str
    publication_year: int | None


def extract_pdf_book_metadata(path: Path, filename: str) -> ExtractedBookMetadata:
    """Read embedded metadata and the first page, falling back without raising."""
    try:
        with pymupdf.open(path) as document:
            metadata = document.metadata or {}
            first_page_text = document[0].get_text("text") if len(document) else ""
    except (OSError, RuntimeError, pymupdf.FileDataError):
        return resolve_book_metadata({}, "", filename)
    return resolve_book_metadata(metadata, first_page_text, filename)


def resolve_book_metadata(
    metadata: Mapping[str, str | None], first_page_text: str, filename: str
) -> ExtractedBookMetadata:
    """Resolve display metadata from values that are easy to test independently."""
    fallback_title = _humanize_filename(filename)
    title = _clean(metadata.get("title")) or fallback_title
    author = _clean(metadata.get("author"))
    if not _is_plausible_author(author):
        author = _author_from_cover(first_page_text, title)
    return ExtractedBookMetadata(
        title=title[:255],
        author=author if author else UNKNOWN_AUTHOR,
        publication_year=_publication_year(metadata, first_page_text),
    )


def _humanize_filename(filename: str) -> str:
    stem = Path(filename).stem
    value = re.sub(r"[_]+", " ", stem).strip()
    return value[:255] or "Untitled book"


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).strip(" -–—")


def _is_plausible_author(value: str) -> bool:
    normalized = value.casefold()
    return bool(value) and normalized not in {"unknown", "unknown author", "anonymous", "none"}


def _author_from_cover(text: str, title: str) -> str:
    cover_text = re.sub(r"[\t\f\v ]+", " ", text).strip()
    if not cover_text:
        return ""
    labeled = _AUTHOR_LABEL.search(cover_text)
    if labeled:
        candidate = _clean(labeled.group(1))
        if _is_plausible_author(candidate):
            return _format_author(candidate)

    title_words = [word for word in re.findall(r"[\w]+", title.casefold()) if len(word) > 1]
    if not title_words:
        return ""
    title_pattern = r"[\W_]+".join(re.escape(word) for word in title_words)
    match = re.search(title_pattern, cover_text, flags=re.IGNORECASE)
    if not match:
        return ""
    trailing = cover_text[match.end() :].splitlines()[0][:100]
    for pattern in (_UPPERCASE_NAME, _TITLECASE_NAME):
        candidate_match = pattern.search(trailing)
        if not candidate_match:
            continue
        candidate = _clean(candidate_match.group(1))
        if _is_plausible_author(candidate) and not any(word in candidate.upper() for word in _NOT_A_NAME):
            return _format_author(candidate)
    return ""


def _format_author(value: str) -> str:
    return value.title() if value.isupper() else value


def _publication_year(metadata: Mapping[str, str | None], first_page_text: str) -> int | None:
    for key in ("publicationYear", "publication_year", "year"):
        value = _clean(metadata.get(key))
        if value and re.fullmatch(r"\d{4}", value) and _is_plausible_year(int(value)):
            return int(value)
    evidence = "\n".join(
        value for value in (metadata.get("subject"), metadata.get("keywords"), first_page_text) if value
    )
    match = re.search(
        r"(?:©|copyright|published|publication(?:\s+date)?)\D{0,24}([12]\d{3})",
        evidence,
        flags=re.IGNORECASE,
    )
    if match and _is_plausible_year(int(match.group(1))):
        return int(match.group(1))
    return None


def _is_plausible_year(value: int) -> bool:
    return 1400 <= value <= 2100
