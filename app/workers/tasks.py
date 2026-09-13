import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.book import Book
from app.services.audio_chunk_store import SQLAlchemyAudioChunkStore
from app.services.audio_generation import AudioChunkGenerator, NarrationChunker
from app.services.book_structure import BookStructureBuilder
from app.services.book_structure_processor import BookStructureProcessor
from app.services.book_structure_store import SQLAlchemyBookStructureStore
from app.services.pdf_parser import PDFParser
from app.services.progressive_processing import ProgressiveProcessingPlanner
from app.services.progressive_processing_coordinator import ProgressiveProcessingCoordinator
from app.services.progressive_processing_store import SQLAlchemyProgressiveProcessingStore
from app.services.resilient_tts import AudioChunkProcessingError, ResilientTTSProcessor
from app.services.storage import get_object_storage
from app.services.tts import ReadingStyle, SpeechRequest, SpeechSpeed, get_tts_synthesizer
from app.services.tts_usage import TTSUsageCostCalculator
from app.workers.celery_app import celery_app


@celery_app.task(name="ai_reader.healthcheck")
def healthcheck() -> dict[str, str]:
    """Minimal task that verifies a worker can consume jobs."""
    return {"status": "ok"}


@celery_app.task(name="ai_reader.books.build_structure")
def build_book_structure(book_id: str) -> dict[str, int | str]:
    """Parse a stored PDF and persist its chapter/content-chunk structure."""
    return asyncio.run(_build_book_structure(UUID(book_id)))


async def _build_book_structure(book_id: UUID) -> dict[str, int | str]:
    async with SessionLocal() as session:
        book = await session.get(Book, book_id)
    if book is None:
        raise ValueError(f"Book {book_id} was not found")

    document = PDFParser().parse_stored_pdf(get_object_storage(), book.storage_key)
    chapters = await BookStructureProcessor(
        BookStructureBuilder(),
        SQLAlchemyBookStructureStore(),
    ).create(book_id, document)
    return {
        "book_id": str(book_id),
        "queued_chapters": len(chapters),
        "queued_content_chunks": sum(len(chapter.chunks) for chapter in chapters),
    }


@celery_app.task(name="ai_reader.processing.plan_book")
def plan_book_processing(book_id: str) -> dict[str, object]:
    """Return the priority-aware work plan without blocking playback."""
    return asyncio.run(_plan_book_processing(UUID(book_id)))


async def _plan_book_processing(book_id: UUID) -> dict[str, object]:
    settings = get_settings()
    plan = await ProgressiveProcessingCoordinator(
        ProgressiveProcessingPlanner(
            priority_chapter_count=settings.progressive_priority_chapter_count,
            playback_min_ready_duration_milliseconds=(
                settings.playback_min_ready_duration_seconds * 1_000
            ),
        ),
        SQLAlchemyProgressiveProcessingStore(),
    ).plan(book_id)
    return {"book_id": str(book_id), **plan.as_task_payload()}


async def _book_tts_preferences(book_id: UUID) -> tuple[str | None, str | None, str | None]:
    async with SessionLocal() as session:
        book = await session.get(Book, book_id)
    if book is None:
        return None, None, None
    return book.tts_voice, book.tts_speed, book.tts_style


@celery_app.task(name="ai_reader.tts.synthesize")
def synthesize_tts(
    text: str,
    *,
    voice: str | None = None,
    speed: str = SpeechSpeed.NORMAL.value,
    style: str = ReadingStyle.NEUTRAL.value,
) -> dict[str, str | int]:
    """Generate one TTS result in the dedicated ``tts`` queue."""
    request = SpeechRequest(
        text=text,
        voice=voice,
        speed=SpeechSpeed(speed),
        style=ReadingStyle(style),
    )
    return get_tts_synthesizer().synthesize(request).as_task_payload()


@celery_app.task(
    bind=True,
    name="ai_reader.tts.generate_chunks",
    autoretry_for=(AudioChunkProcessingError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": get_settings().tts_max_attempts - 1},
)
def generate_audio_chunks(
    self,
    book_id: str,
    narration: str,
    *,
    voice: str | None = None,
    speed: str | None = None,
    style: str | None = None,
) -> dict[str, object]:
    """Generate TTS chunks with per-chunk checkpoints and retry support."""
    parsed_book_id = UUID(book_id)
    settings = get_settings()
    book_voice, book_speed, book_style = asyncio.run(_book_tts_preferences(parsed_book_id))
    generator = AudioChunkGenerator(
        get_tts_synthesizer(),
        get_object_storage(),
        chunker=NarrationChunker(settings.tts_chunk_max_characters),
    )
    processor = ResilientTTSProcessor(
        generator,
        SQLAlchemyAudioChunkStore(),
        cost_calculator=TTSUsageCostCalculator(settings),
    )
    chunks = asyncio.run(
        processor.process(
            parsed_book_id,
            narration,
            voice=voice or book_voice or settings.tts_voice,
            speed=SpeechSpeed(speed or book_speed or SpeechSpeed.NORMAL.value),
            style=ReadingStyle(style or book_style or ReadingStyle.NEUTRAL.value),
            attempt_count=self.request.retries + 1,
        )
    )
    return {"book_id": book_id, "chunks": [chunk.as_task_payload() for chunk in chunks]}
