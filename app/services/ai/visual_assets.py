"""Extract image crops for vision-capable narration requests."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.services.documents.pdf_parser import VisualBlock


class VisualExtractionError(RuntimeError):
    """Raised when a visual block cannot be rendered from its source PDF."""


@dataclass(frozen=True)
class VisualAsset:
    visual: VisualBlock
    image_data: bytes
    media_type: str = "image/png"
    context: str = ""


class PDFVisualExtractor:
    """Renders a detected PDF visual block to PNG for the AI vision input."""

    render_scale = 2

    def extract(self, source: Path, visual: VisualBlock, context: str = "") -> VisualAsset:
        try:
            with pymupdf.open(source) as document:
                page = document[visual.page_number - 1]
                clip = pymupdf.Rect(visual.bbox) & page.rect
                if clip.is_empty:
                    raise VisualExtractionError("Visual block is outside the PDF page")
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(self.render_scale, self.render_scale),
                    clip=clip,
                    alpha=False,
                )
        except (IndexError, OSError, RuntimeError, pymupdf.FileDataError) as error:
            raise VisualExtractionError(
                f"Unable to render visual on page {visual.page_number}"
            ) from error

        return VisualAsset(
            visual=visual,
            image_data=pixmap.tobytes("png"),
            context=context,
        )
