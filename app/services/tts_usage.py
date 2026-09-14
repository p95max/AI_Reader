"""Provider-neutral measurement and costing for generated speech."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class TTSUsageCost:
    generated_audio_milliseconds: int
    generation_time_milliseconds: int
    external_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return self.external_cost_usd


class TTSUsageCostCalculator:
    """Calculate actual TTS cost from measurable audio and compute durations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def calculate(
        self,
        *,
        generated_audio_milliseconds: int,
        generation_time_milliseconds: int,
    ) -> TTSUsageCost:
        if generated_audio_milliseconds < 0 or generation_time_milliseconds < 0:
            raise ValueError("TTS durations must not be negative")

        external_cost = (
            generated_audio_milliseconds
            * self._settings.tts_external_cost_per_audio_hour_usd
            / 3_600_000
        )
        return TTSUsageCost(
            generated_audio_milliseconds=generated_audio_milliseconds,
            generation_time_milliseconds=generation_time_milliseconds,
            external_cost_usd=round(external_cost, 8),
        )
