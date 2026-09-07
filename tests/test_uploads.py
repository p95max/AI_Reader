import io

import pytest
from starlette.datastructures import Headers, UploadFile

from app.services.uploads import InvalidPDFUpload, UploadTooLarge, persist_pdf_upload


def make_upload(content: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        filename="chapter.pdf",
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_persist_pdf_upload_writes_valid_pdf() -> None:
    path, size_bytes = await persist_pdf_upload(make_upload(b"%PDF-1.7\\ncontent"), 1024)

    try:
        assert path.read_bytes() == b"%PDF-1.7\\ncontent"
        assert size_bytes == len(b"%PDF-1.7\\ncontent")
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_persist_pdf_upload_rejects_invalid_signature() -> None:
    with pytest.raises(InvalidPDFUpload):
        await persist_pdf_upload(make_upload(b"not-a-pdf"), 1024)


@pytest.mark.asyncio
async def test_persist_pdf_upload_rejects_large_file() -> None:
    with pytest.raises(UploadTooLarge):
        await persist_pdf_upload(make_upload(b"%PDF-" + b"x" * 20), 16)
