import pytest

from app.core.config import Settings
from app.services.audio.tts_usage import TTSUsageCostCalculator


def test_tts_usage_calculates_external_audio_cost() -> None:
    calculator = TTSUsageCostCalculator(
        Settings(
            tts_external_cost_per_audio_hour_usd=3.6,
        )
    )

    usage = calculator.calculate(
        generated_audio_milliseconds=1_800_000,
        generation_time_milliseconds=900_000,
    )

    assert usage.external_cost_usd == pytest.approx(1.8)
    assert usage.total_cost_usd == pytest.approx(1.8)


@pytest.mark.parametrize("audio_ms,generation_ms", [(-1, 0), (0, -1)])
def test_tts_usage_rejects_negative_durations(audio_ms: int, generation_ms: int) -> None:
    with pytest.raises(ValueError, match="durations must not be negative"):
        TTSUsageCostCalculator(Settings()).calculate(
            generated_audio_milliseconds=audio_ms,
            generation_time_milliseconds=generation_ms,
        )
