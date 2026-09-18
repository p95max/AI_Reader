import logging
from uuid import UUID

import pytest

from app.core.config import Settings
from app.services.audio.audio_chunk_store import VoiceMismatchError
from app.services.audio.audio_generation import GeneratedAudioChunk
from app.services.audio.resilient_tts import (
    AudioChunkProcessingError,
    ResilientTTSProcessor,
    TTSBudgetLimitExceeded,
)
from app.services.audio.tts import SpeechSpeed, TTSError
from app.services.audio.tts_usage import TTSUsageCostCalculator

BOOK_ID = UUID("12345678-1234-5678-1234-567812345678")


class FakeGenerator:
    def __init__(self, *, failure_index: int | None = None) -> None:
        self.failure_index = failure_index
        self.generated_indexes: list[int] = []
        self.tts_provider = "openai"
        self.tts_model = "gpt-4o-mini-tts"
        self.deleted_storage_keys: list[str] = []

    def split_narration(self, _narration: str) -> list[str]:
        return ["First chunk.", "Second chunk."]

    def generate_chunk(
        self, _book_id: UUID, index: int, text: str, **_kwargs: object
    ) -> GeneratedAudioChunk:
        self.generated_indexes.append(index)
        if index == self.failure_index:
            raise TTSError("provider unavailable")
        return GeneratedAudioChunk(
            chunk_index=index,
            narration=text,
            storage_key=f"books/{BOOK_ID}/audio/{index:06d}.wav",
            content_type="audio/wav",
            duration_milliseconds=1_000,
        )

    def delete_chunk(self, storage_key: str) -> None:
        self.deleted_storage_keys.append(storage_key)


class MemoryCheckpointStore:
    def __init__(self, *, ready: set[int] | None = None, voice: str | None = None) -> None:
        self.ready = ready or set()
        self.voice = voice
        self.ready_calls: list[tuple[GeneratedAudioChunk, str, int, int, float]] = []
        self.failed_calls: list[dict[str, object]] = []
        self.fail_mark_ready = False

    async def ensure_voice(self, _book_id: UUID, voice: str) -> None:
        if self.voice is not None and self.voice != voice:
            raise VoiceMismatchError("voice mismatch")
        self.voice = voice

    async def is_ready(self, _book_id: UUID, chunk_index: int) -> bool:
        return chunk_index in self.ready

    async def ready_tts_cost_usd(self, _book_id: UUID) -> float:
        return sum(call[4] for call in self.ready_calls)

    async def mark_ready(
        self,
        _book_id: UUID,
        chunk: GeneratedAudioChunk,
        *,
        voice: str,
        tts_provider: str | None,
        tts_model: str | None,
        attempt_count: int,
        generation_time_milliseconds: int,
        tts_cost_usd: float,
    ) -> None:
        if self.fail_mark_ready:
            raise RuntimeError("database checkpoint failed")
        self.ready.add(chunk.chunk_index)
        self.ready_calls.append(
            (chunk, voice, attempt_count, generation_time_milliseconds, tts_cost_usd)
        )

    async def mark_failed(self, _book_id: UUID, **kwargs: object) -> None:
        self.failed_calls.append(kwargs)


@pytest.mark.asyncio
async def test_restart_skips_chunks_that_are_already_ready(
    caplog: pytest.LogCaptureFixture,
) -> None:
    generator = FakeGenerator()
    store = MemoryCheckpointStore(ready={0}, voice="Narrator")
    processor = ResilientTTSProcessor(
        generator,
        store,  # type: ignore[arg-type]
        cost_calculator=TTSUsageCostCalculator(
            Settings(tts_external_cost_per_audio_hour_usd=3_600)
        ),
    )

    with caplog.at_level(logging.INFO):
        chunks = await processor.process(
            BOOK_ID,
            "narration",
            voice="Narrator",
            speed=SpeechSpeed.NORMAL,
            attempt_count=2,
        )

    assert generator.generated_indexes == [1]
    assert [chunk.chunk_index for chunk in chunks] == [1]
    assert store.ready_calls[0][2] == 2
    assert store.ready_calls[0][4] == pytest.approx(1.0)
    assert "tts_chunk_skipped_ready" in caplog.messages
    assert "tts_chunk_generated" in caplog.messages


@pytest.mark.asyncio
async def test_failed_chunk_is_checkpointed_for_retry(caplog: pytest.LogCaptureFixture) -> None:
    generator = FakeGenerator(failure_index=1)
    store = MemoryCheckpointStore(ready={0}, voice="Narrator")
    processor = ResilientTTSProcessor(generator, store)  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR), pytest.raises(AudioChunkProcessingError):
        await processor.process(
            BOOK_ID,
            "narration",
            voice="Narrator",
            speed=SpeechSpeed.SLOW,
            attempt_count=3,
        )

    assert generator.generated_indexes == [1]
    assert store.failed_calls == [
        {
            "chunk_index": 1,
            "narration": "Second chunk.",
            "storage_key": f"books/{BOOK_ID}/audio/000001.wav",
            "voice": "Narrator",
            "tts_provider": "openai",
            "tts_model": "gpt-4o-mini-tts",
            "attempt_count": 3,
            "error_message": "provider unavailable",
        }
    ]
    assert "tts_chunk_generation_failed" in caplog.messages


@pytest.mark.asyncio
async def test_voice_mismatch_blocks_new_audio_generation() -> None:
    generator = FakeGenerator()
    processor = ResilientTTSProcessor(generator, MemoryCheckpointStore(voice="Other"))  # type: ignore[arg-type]

    with pytest.raises(VoiceMismatchError, match="voice mismatch"):
        await processor.process(
            BOOK_ID,
            "narration",
            voice="Narrator",
            speed=SpeechSpeed.NORMAL,
            attempt_count=1,
        )

    assert generator.generated_indexes == []


@pytest.mark.asyncio
async def test_failed_checkpoint_removes_uploaded_audio_object() -> None:
    generator = FakeGenerator()
    store = MemoryCheckpointStore()
    store.fail_mark_ready = True
    processor = ResilientTTSProcessor(generator, store)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="database checkpoint failed"):
        await processor.process(
            BOOK_ID,
            "narration",
            voice="Narrator",
            speed=SpeechSpeed.NORMAL,
            attempt_count=1,
        )

    assert generator.deleted_storage_keys == [f"books/{BOOK_ID}/audio/000000.wav"]


@pytest.mark.asyncio
async def test_tts_budget_blocks_provider_request_before_new_audio_is_charged() -> None:
    generator = FakeGenerator()
    store = MemoryCheckpointStore()
    processor = ResilientTTSProcessor(
        generator,
        store,  # type: ignore[arg-type]
        cost_calculator=TTSUsageCostCalculator(
            Settings(tts_external_cost_per_audio_hour_usd=3_600)
        ),
    )

    with pytest.raises(TTSBudgetLimitExceeded, match="budget"):
        await processor.process(
            BOOK_ID,
            "narration",
            voice="Narrator",
            speed=SpeechSpeed.NORMAL,
            attempt_count=1,
            max_tts_cost_usd=0.5,
        )

    assert generator.generated_indexes == []
    assert store.ready_calls == []
