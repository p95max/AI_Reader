"""Coordinates live database state with the progressive-processing policy."""

from __future__ import annotations

from uuid import UUID

from app.services.documents.progressive_processing import ProgressivePlan, ProgressiveProcessingPlanner
from app.services.documents.progressive_processing_store import SQLAlchemyProgressiveProcessingStore


class ProgressiveProcessingCoordinator:
    def __init__(
        self,
        planner: ProgressiveProcessingPlanner,
        store: SQLAlchemyProgressiveProcessingStore,
    ) -> None:
        self._planner = planner
        self._store = store

    async def plan(self, book_id: UUID) -> ProgressivePlan:
        pending_chunks = await self._store.pending_chunks(book_id)
        ready_duration = await self._store.ready_audio_duration_milliseconds(book_id)
        return self._planner.plan(
            pending_chunks,
            ready_audio_duration_milliseconds=ready_duration,
        )
