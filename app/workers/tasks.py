import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.services.audio_chunk_store import SQLAlchemyAudioChunkStore
from app.services.audio_generation import AudioChunkGenerator, NarrationChunker
from app.services.resilient_tts import AudioChunkProcessingError, ResilientTTSProcessor
from app.services.storage import get_object_storage
from app.services.tts import SpeechRequest, SpeechSpeed, get_tts_synthesizer
from app.workers.celery_app import celery_app


@celery_app.task(name="ai_reader.healthcheck")
def healthcheck() -> dict[str, str]:
    """Minimal task that verifies a worker can consume jobs."""
    return {"status": "ok"}


@celery_app.task(name="ai_reader.tts.synthesize")
def synthesize_tts(
    text: str,
    *,
    voice: str | None = None,
    speed: str = SpeechSpeed.NORMAL.value,
) -> dict[str, str | int]:
    """Generate one TTS result in the dedicated ``tts`` queue."""
    request = SpeechRequest(text=text, voice=voice, speed=SpeechSpeed(speed))
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
    speed: str = SpeechSpeed.NORMAL.value,
) -> dict[str, object]:
    """Generate TTS chunks with per-chunk checkpoints and retry support."""
    parsed_book_id = UUID(book_id)
    settings = get_settings()
    generator = AudioChunkGenerator(
        get_tts_synthesizer(),
        get_object_storage(),
        chunker=NarrationChunker(settings.tts_chunk_max_characters),
    )
    processor = ResilientTTSProcessor(generator, SQLAlchemyAudioChunkStore())
    chunks = asyncio.run(
        processor.process(
            parsed_book_id,
            narration,
            voice=voice or settings.tts_voice,
            speed=SpeechSpeed(speed),
            attempt_count=self.request.retries + 1,
        )
    )
    return {"book_id": book_id, "chunks": [chunk.as_task_payload() for chunk in chunks]}
