"""Priority and playback policy for progressive book processing."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

HIGH_PRIORITY = 9
NORMAL_PRIORITY = 0


@dataclass(frozen=True, slots=True)
class PendingContentChunk:
    id: UUID
    chapter_index: int
    chunk_index: int


@dataclass(frozen=True, slots=True)
class PrioritizedContentChunk:
    id: UUID
    chapter_index: int
    chunk_index: int
    priority: int


@dataclass(frozen=True, slots=True)
class ProgressivePlan:
    chunks: tuple[PrioritizedContentChunk, ...]
    ready_audio_duration_milliseconds: int
    playback_ready: bool
    continue_generation_in_background: bool

    def as_task_payload(self) -> dict[str, object]:
        return {
            "ready_audio_duration_milliseconds": self.ready_audio_duration_milliseconds,
            "playback_ready": self.playback_ready,
            "continue_generation_in_background": self.continue_generation_in_background,
            "chunks": [
                {
                    "content_chunk_id": str(chunk.id),
                    "chapter_index": chunk.chapter_index,
                    "chunk_index": chunk.chunk_index,
                    "priority": chunk.priority,
                }
                for chunk in self.chunks
            ],
        }


class ProgressiveProcessingPlanner:
    """Prioritizes a book's beginning without stopping later background work."""

    def __init__(
        self,
        *,
        priority_chapter_count: int,
        playback_min_ready_duration_milliseconds: int,
    ) -> None:
        if priority_chapter_count < 1:
            raise ValueError("priority_chapter_count must be positive")
        if playback_min_ready_duration_milliseconds < 1:
            raise ValueError("playback readiness duration must be positive")
        self._priority_chapter_count = priority_chapter_count
        self._playback_min_ready_duration_milliseconds = playback_min_ready_duration_milliseconds

    def plan(
        self,
        pending_chunks: tuple[PendingContentChunk, ...],
        *,
        ready_audio_duration_milliseconds: int,
    ) -> ProgressivePlan:
        if ready_audio_duration_milliseconds < 0:
            raise ValueError("ready audio duration must not be negative")
        prioritized = tuple(
            sorted(
                (
                    PrioritizedContentChunk(
                        id=chunk.id,
                        chapter_index=chunk.chapter_index,
                        chunk_index=chunk.chunk_index,
                        priority=(
                            HIGH_PRIORITY
                            if chunk.chapter_index < self._priority_chapter_count
                            else NORMAL_PRIORITY
                        ),
                    )
                    for chunk in pending_chunks
                ),
                key=lambda chunk: (-chunk.priority, chunk.chapter_index, chunk.chunk_index),
            )
        )
        playback_ready = (
            ready_audio_duration_milliseconds >= self._playback_min_ready_duration_milliseconds
        )
        return ProgressivePlan(
            chunks=prioritized,
            ready_audio_duration_milliseconds=ready_audio_duration_milliseconds,
            playback_ready=playback_ready,
            continue_generation_in_background=playback_ready and bool(prioritized),
        )
