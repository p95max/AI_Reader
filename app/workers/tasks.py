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
