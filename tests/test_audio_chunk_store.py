from uuid import UUID

import pytest

from app.services.audio.audio_chunk_store import SQLAlchemyAudioChunkStore
from app.services.audio.audio_generation import GeneratedAudioChunk


class FakeSession:
    def __init__(self) -> None:
        self.records: list[object] = []
        self.committed = False

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def add_all(self, records: list[object]) -> None:
        self.records.extend(records)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_store_persists_measured_duration_and_object_key() -> None:
    session = FakeSession()
    store = SQLAlchemyAudioChunkStore(session_factory=lambda: session)  # type: ignore[arg-type]
    chunk = GeneratedAudioChunk(
        chunk_index=4,
        narration="Готовый narration.",
        storage_key="books/book/audio/000004.wav",
        content_type="audio/wav",
        duration_milliseconds=1_234,
        tts_provider="openai",
        tts_model="gpt-4o-mini-tts",
    )

    await store.save_many(UUID("12345678-1234-5678-1234-567812345678"), [chunk])

    assert session.committed is True
    record = session.records[0]
    assert record.duration_milliseconds == 1_234
    assert record.storage_key == "books/book/audio/000004.wav"
    assert record.tts_provider == "openai"
    assert record.tts_model == "gpt-4o-mini-tts"
