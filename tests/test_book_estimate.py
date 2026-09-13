import pytest

from app.services.book_estimate import estimate_book_processing


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
    assert estimate.estimated_audio_seconds > 0


@pytest.mark.parametrize("size", [0, -1])
def test_estimate_rejects_invalid_file_size(size: int) -> None:
    with pytest.raises(ValueError, match="file size must be positive"):
        estimate_book_processing(
            size,
            input_cost_per_million_tokens=0,
            output_cost_per_million_tokens=0,
        )
