import io

import pymupdf
import pytest
from starlette.datastructures import Headers, UploadFile

from app.services.documents.uploads import (
    InvalidPDFUpload,
    PDFPageLimitExceeded,
    UploadTooLarge,
    persist_pdf_upload,
)


def pdf_bytes(page_count: int = 1) -> bytes:
    document = pymupdf.open()
    for _ in range(page_count):
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def make_upload(content: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        filename="chapter.pdf",
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_persist_pdf_upload_writes_valid_pdf() -> None:
    content = pdf_bytes()
    path, size_bytes = await persist_pdf_upload(make_upload(content), 1024 * 1024, 500)

    try:
        assert path.read_bytes() == content
        assert size_bytes == len(content)
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_persist_pdf_upload_rejects_invalid_signature() -> None:
    with pytest.raises(InvalidPDFUpload):
        await persist_pdf_upload(make_upload(b"not-a-pdf"), 1024, 500)


@pytest.mark.asyncio
async def test_persist_pdf_upload_rejects_large_file() -> None:
    with pytest.raises(UploadTooLarge):
        await persist_pdf_upload(make_upload(pdf_bytes()), 16, 500)


@pytest.mark.asyncio
async def test_persist_pdf_upload_rejects_too_many_pages() -> None:
    with pytest.raises(PDFPageLimitExceeded):
        await persist_pdf_upload(make_upload(pdf_bytes(page_count=2)), 1024 * 1024, 1)
