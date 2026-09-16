from pathlib import Path

import pymupdf

from app.services.ai.visual_assets import PDFVisualExtractor
from app.services.documents.pdf_parser import VisualBlock


def test_visual_extractor_renders_pdf_block_as_png(tmp_path: Path) -> None:
    source = tmp_path / "visual.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(72, 72, 180, 140), color=(0, 0, 0), fill=(0.2, 0.5, 0.8))
        document.save(source)

    asset = PDFVisualExtractor().extract(
        source,
        VisualBlock(page_number=1, bbox=(72, 72, 180, 140), kind="diagram"),
        context="Flow diagram",
    )

    assert asset.media_type == "image/png"
    assert asset.image_data.startswith(b"\x89PNG")
    assert asset.context == "Flow diagram"
