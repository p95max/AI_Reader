import os
import tempfile
from pathlib import Path

from fastapi import UploadFile


class InvalidPDFUpload(ValueError):
    """Raised when an upload is not a PDF."""


class UploadTooLarge(ValueError):
    """Raised when an upload exceeds the configured maximum size."""


async def persist_pdf_upload(upload: UploadFile, max_size_bytes: int) -> tuple[Path, int]:
    """Stream a PDF upload to a temporary file and validate its size and signature."""
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

    return path, size_bytes
