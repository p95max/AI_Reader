"""Fast, pre-upload estimates for processing a technical PDF."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import ModelPricing


@dataclass(frozen=True, slots=True)
class BookProcessingEstimate:
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_ai_cost_usd: float
    estimated_tts_cost_usd: float
    estimated_total_cost_usd: float
    estimated_audio_seconds: int


def estimate_book_processing(
    file_size_bytes: int,
    *,
    input_cost_per_million_tokens: float,
    output_cost_per_million_tokens: float,
    tts_cost_per_audio_hour_usd: float = 0.0,
) -> BookProcessingEstimate:
    """Estimate processing before extraction; a parsed PDF supersedes this rough estimate."""
    if file_size_bytes < 1:
        raise ValueError("file size must be positive")
    if (
        input_cost_per_million_tokens < 0
        or output_cost_per_million_tokens < 0
        or tts_cost_per_audio_hour_usd < 0
    ):
        raise ValueError("token costs must not be negative")

    # Text PDFs commonly encode several bytes per token. This deliberately remains a
    # coarse estimate because scanned PDFs and embedded images change the ratio widely.
    estimated_input_tokens = max(1_000, round(file_size_bytes / 8))
    estimated_output_tokens = round(estimated_input_tokens * 0.25)
    estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
    estimated_audio_seconds = round(estimated_total_tokens * 0.28)
    estimated_tts_cost_usd = round(
        estimated_audio_seconds / 3_600 * tts_cost_per_audio_hour_usd,
        4,
    )
    estimated_ai_cost_usd = round(
        (
            estimated_input_tokens * input_cost_per_million_tokens
            + estimated_output_tokens * output_cost_per_million_tokens
        )
        / 1_000_000,
        4,
    )
    return BookProcessingEstimate(
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_total_tokens=estimated_total_tokens,
        estimated_ai_cost_usd=estimated_ai_cost_usd,
        estimated_tts_cost_usd=estimated_tts_cost_usd,
        estimated_total_cost_usd=round(estimated_ai_cost_usd + estimated_tts_cost_usd, 4),
        estimated_audio_seconds=estimated_audio_seconds,
    )


def estimate_book_processing_with_pricing(
    file_size_bytes: int,
    *,
    pricing: ModelPricing,
    tts_cost_per_audio_hour_usd: float = 0.0,
) -> BookProcessingEstimate:
    """Use a selected model's versioned price list for the pre-processing estimate."""
    return estimate_book_processing(
        file_size_bytes,
        input_cost_per_million_tokens=pricing.input_per_million_tokens,
        output_cost_per_million_tokens=pricing.output_per_million_tokens,
        tts_cost_per_audio_hour_usd=tts_cost_per_audio_hour_usd,
    )
