from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

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

    def add(self, record: object) -> None:
        self.records.append(record)

    def add_all(self, records: list[object]) -> None:
        self.records.extend(records)

    async def rollback(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_store_persists_measured_duration_and_object_key() -> None:
    session = FakeSession()
    store = SQLAlchemyAudioChunkStore(session_factory=lambda: session)  # type: ignore[arg-type]
    chunk = GeneratedAudioChunk(
        chunk_index=4,
        narration="Completed narration.",
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


@pytest.mark.asyncio
async def test_store_ignores_fk_violation_when_book_was_deleted_during_processing() -> None:
    class RaceConditionSession(FakeSession):
        async def commit(self) -> None:
            raise IntegrityError(
                "INSERT INTO audio_chunks ...",
                {},
                Exception(
                    'insert or update on table "audio_chunks" violates foreign key constraint "audio_chunks_book_id_fkey"'
                ),
            )

        async def scalar(self, _statement: object) -> None:
            return None

    store = SQLAlchemyAudioChunkStore(session_factory=lambda: RaceConditionSession())  # type: ignore[arg-type]

    await store.mark_failed(
        UUID("12345678-1234-5678-1234-567812345678"),
        chunk_index=5,
        narration="Narration",
        storage_key="books/book/audio/000005.wav",
        voice="alloy",
        tts_provider="openai",
        tts_model="gpt-4o-mini-tts",
        attempt_count=1,
        error_message="Connection error.",
    )
