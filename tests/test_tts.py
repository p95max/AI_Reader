import io
import wave

import pytest

from app.core.config import get_settings
from app.services.audio.resilient_tts import AudioChunkProcessingError
from app.services.audio.tts import (
    OpenAITTSSynthesizer,
    ReadingStyle,
    SpeechRequest,
    SpeechSpeed,
    speech_instruction,
)
from app.workers.celery_app import celery_app
from app.workers.tasks import _is_final_attempt, generate_audio_chunks


class FakeOpenAIResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content


class FakeOpenAISpeech:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> FakeOpenAIResponse:
        self.calls.append(kwargs)
        return FakeOpenAIResponse(self.content)


class FakeOpenAIClient:
    def __init__(self, content: bytes) -> None:
        self.audio = type("Audio", (), {"speech": FakeOpenAISpeech(content)})()


def wav_bytes(sample_rate: int = 24_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * 16)
    return output.getvalue()


def test_openai_tts_maps_existing_voice_and_returns_wav() -> None:
    client = FakeOpenAIClient(wav_bytes())
    settings = get_settings().model_copy(
        update={"tts_openai_model": "gpt-4o-mini-tts", "tts_openai_slow_speed": 0.8}
    )

    result = OpenAITTSSynthesizer(settings, client=client).synthesize(
        SpeechRequest(text="Test", voice="Vivian", speed=SpeechSpeed.SLOW)
    )

    call = client.audio.speech.calls[0]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "nova"
    assert call["speed"] == 0.8
    assert call["response_format"] == "wav"
    assert result.sample_rate == 24_000


def test_openai_tts_rejects_unknown_voice_before_call() -> None:
    client = FakeOpenAIClient(wav_bytes())
    with pytest.raises(Exception, match="Unknown OpenAI TTS voice"):
        OpenAITTSSynthesizer(get_settings(), client=client).synthesize(
            SpeechRequest(text="Test", voice="unsupported")
        )
    assert client.audio.speech.calls == []


def test_slow_mode_changes_the_speech_instruction() -> None:
    settings = get_settings()
    assert "more slowly" in speech_instruction(settings, SpeechSpeed.SLOW)
    assert "natural" in speech_instruction(settings, SpeechSpeed.NORMAL)


def test_reading_style_changes_the_speech_instruction() -> None:
    settings = get_settings()

    assert "calm" in speech_instruction(settings, SpeechSpeed.NORMAL, ReadingStyle.CALM)
    assert "expressive" in speech_instruction(settings, SpeechSpeed.NORMAL, ReadingStyle.EXPRESSIVE)


def test_tts_tasks_are_routed_to_a_dedicated_queue() -> None:
    route = celery_app.conf.task_routes["ai_reader.tts.*"]
    assert route["queue"] == "tts"


def test_chunk_generation_retries_only_retryable_failures() -> None:
    assert generate_audio_chunks.autoretry_for == (AudioChunkProcessingError,)
    assert generate_audio_chunks.retry_kwargs == {"max_retries": 2}
    assert generate_audio_chunks.retry_backoff is True


def test_retryable_chunk_is_only_failed_after_its_last_attempt() -> None:
    assert not _is_final_attempt(
        retries=0,
        max_attempts=3,
        error=TimeoutError(),
        retryable_errors=(TimeoutError,),
    )
    assert _is_final_attempt(
        retries=2,
        max_attempts=3,
        error=TimeoutError(),
        retryable_errors=(TimeoutError,),
    )
    assert _is_final_attempt(
        retries=0,
        max_attempts=3,
        error=ValueError(),
        retryable_errors=(TimeoutError,),
    )


def test_empty_speech_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SpeechRequest(text="   ")
