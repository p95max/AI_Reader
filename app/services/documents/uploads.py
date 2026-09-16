import os
import tempfile
from pathlib import Path

import pymupdf
from fastapi import UploadFile


class InvalidPDFUpload(ValueError):
    """Raised when an upload is not a PDF."""


class UploadTooLarge(ValueError):
    """Raised when an upload exceeds the configured maximum size."""


class PDFPageLimitExceeded(ValueError):
    """Raised when a PDF contains more pages than the service accepts."""


def pdf_page_count(path: Path) -> int:
    """Read the validated PDF page count for processing-range selection."""
    with pymupdf.open(path) as document:
        return document.page_count


async def persist_pdf_upload(
    upload: UploadFile,
    max_size_bytes: int,
    max_pages: int,
) -> tuple[Path, int]:
    """Stream a PDF upload and verify its real format, size, and page count."""
    descriptor, raw_path = tempfile.mkstemp(suffix=".pdf")
    path = Path(raw_path)
    size_bytes = 0
    signature = b""

    try:
        with os.fdopen(descriptor, "wb") as destination:
            while chunk := await upload.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise UploadTooLarge
                if len(signature) < 5:
                    signature += chunk[: 5 - len(signature)]
                destination.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if not signature.startswith(b"%PDF-"):
        path.unlink(missing_ok=True)
        raise InvalidPDFUpload

    try:
        with pymupdf.open(path) as document:
            if not document.page_count:
                raise InvalidPDFUpload
            if document.page_count > max_pages:
                raise PDFPageLimitExceeded
    except (pymupdf.FileDataError, RuntimeError, OSError) as error:
        path.unlink(missing_ok=True)
        raise InvalidPDFUpload from error
    except PDFPageLimitExceeded:
        path.unlink(missing_ok=True)
        raise

    return path, size_bytes
