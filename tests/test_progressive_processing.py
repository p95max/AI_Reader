from uuid import UUID

import pytest

from app.services.documents.progressive_processing import (
    HIGH_PRIORITY,
    NORMAL_PRIORITY,
    PendingContentChunk,
    ProgressiveProcessingPlanner,
)
from app.workers.celery_app import celery_app


def pending(chapter_index: int, chunk_index: int) -> PendingContentChunk:
    return PendingContentChunk(
        id=UUID(f"00000000-0000-0000-0000-{chapter_index + 1:012d}"),
        chapter_index=chapter_index,
        chunk_index=chunk_index,
    )


def test_book_beginning_is_planned_with_high_priority() -> None:
    planner = ProgressiveProcessingPlanner(
        priority_chapter_count=1,
        playback_min_ready_duration_milliseconds=600_000,
    )

    plan = planner.plan(
        (pending(2, 0), pending(0, 1), pending(0, 0), pending(1, 0)),
        ready_audio_duration_milliseconds=0,
    )

    assert [(chunk.chapter_index, chunk.chunk_index, chunk.priority) for chunk in plan.chunks] == [
        (0, 0, HIGH_PRIORITY),
        (0, 1, HIGH_PRIORITY),
        (1, 0, NORMAL_PRIORITY),
        (2, 0, NORMAL_PRIORITY),
    ]


def test_playback_unblocks_after_ready_audio_threshold_and_work_continues() -> None:
    planner = ProgressiveProcessingPlanner(
        priority_chapter_count=2,
        playback_min_ready_duration_milliseconds=600_000,
    )

    plan = planner.plan((pending(2, 0),), ready_audio_duration_milliseconds=600_000)

    assert plan.playback_ready is True
    assert plan.continue_generation_in_background is True
    assert plan.ready_audio_duration_milliseconds == 600_000


def test_playback_stays_blocked_below_threshold() -> None:
    planner = ProgressiveProcessingPlanner(
        priority_chapter_count=1,
        playback_min_ready_duration_milliseconds=600_000,
    )

    plan = planner.plan((pending(0, 0),), ready_audio_duration_milliseconds=599_999)

    assert plan.playback_ready is False
    assert plan.continue_generation_in_background is False


def test_invalid_duration_is_rejected() -> None:
    planner = ProgressiveProcessingPlanner(
        priority_chapter_count=1,
        playback_min_ready_duration_milliseconds=1,
    )

    with pytest.raises(ValueError, match="must not be negative"):
        planner.plan((), ready_audio_duration_milliseconds=-1)


def test_progressive_work_uses_its_own_worker_queue() -> None:
    route = celery_app.conf.task_routes["ai_reader.processing.*"]
    assert route["queue"] == "processing"
