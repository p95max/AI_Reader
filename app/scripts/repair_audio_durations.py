"""Repair WAV durations after a provider wrote an invalid WAV data-size header.

Usage:
    python -m app.scripts.repair_audio_durations --book-id <UUID>
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audio_chunk import AudioChunk
from app.services.audio_generation import wav_duration_milliseconds
from app.services.storage import get_object_storage


async def repair_book_audio_durations(book_id: UUID) -> int:
    """Recalculate persisted durations from object bytes and return repaired row count."""
    storage = get_object_storage()
    async with SessionLocal() as session:
        chunks = tuple(
            (
                await session.scalars(
                    select(AudioChunk)
                    .where(AudioChunk.book_id == book_id)
                    .order_by(AudioChunk.chunk_index)
                )
            ).all()
        )
        for chunk in chunks:
            chunk.duration_milliseconds = wav_duration_milliseconds(
                storage.download_bytes(chunk.storage_key)
            )
        await session.commit()
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair stored WAV duration metadata")
    parser.add_argument("--book-id", required=True, type=UUID)
    arguments = parser.parse_args()
    repaired = asyncio.run(repair_book_audio_durations(arguments.book_id))
    print(f"Repaired duration metadata for {repaired} audio chunks")


if __name__ == "__main__":
    main()
