import pytest

from app.core.config import ModelPricing, Settings
from app.services.books.book_estimate import (
    estimate_book_processing,
    estimate_book_processing_with_pricing,
)


def test_estimate_uses_configured_token_pricing() -> None:
    estimate = estimate_book_processing(
        80_000,
        input_cost_per_million_tokens=2.0,
        output_cost_per_million_tokens=8.0,
    )

    assert estimate.estimated_input_tokens == 10_000
    assert estimate.estimated_output_tokens == 2_500
    assert estimate.estimated_total_tokens == 12_500
    assert estimate.estimated_ai_cost_usd == 0.04
    assert estimate.estimated_tts_cost_usd == 0
    assert estimate.estimated_total_cost_usd == 0.04
    assert estimate.estimated_audio_seconds > 0


def test_estimate_includes_external_tts_cost() -> None:
    estimate = estimate_book_processing(
        80_000,
        input_cost_per_million_tokens=2.0,
        output_cost_per_million_tokens=8.0,
        tts_cost_per_audio_hour_usd=0.90,
    )

    # 12,500 estimated tokens correspond to 3,500 seconds of audio at the
    # deliberately conservative pre-extraction speech-duration estimate.
    assert estimate.estimated_tts_cost_usd == 0.875
    assert estimate.estimated_total_cost_usd == 0.915


def test_estimate_uses_versioned_model_price_list() -> None:
    settings = Settings(
        ai_model="gpt-costed",
        ai_input_cost_per_million_tokens=0,
        ai_cached_input_cost_per_million_tokens=0,
        ai_output_cost_per_million_tokens=0,
        ai_pricing_version="default",
        ai_model_price_list={
            "gpt-costed": {
                "input_per_million_tokens": 2.0,
                "cached_input_per_million_tokens": 0.5,
                "output_per_million_tokens": 8.0,
                "version": "2026-09",
            }
        },
    )

    pricing = settings.pricing_for_model()
    estimate = estimate_book_processing_with_pricing(80_000, pricing=pricing)

    assert pricing.version == "2026-09"
    assert estimate.estimated_ai_cost_usd == 0.04
    assert settings.pricing_for_model("unknown") == ModelPricing()


@pytest.mark.parametrize("size", [0, -1])
def test_estimate_rejects_invalid_file_size(size: int) -> None:
    with pytest.raises(ValueError, match="file size must be positive"):
        estimate_book_processing(
            size,
            input_cost_per_million_tokens=0,
            output_cost_per_million_tokens=0,
        )
