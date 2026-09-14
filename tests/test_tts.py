import io
import wave

import pytest

from app.core.config import get_settings
from app.services.resilient_tts import AudioChunkProcessingError
from app.services.tts import (
    OpenAITTSSynthesizer,
    QwenTTSSynthesizer,
    ReadingStyle,
    SpeechRequest,
    SpeechSpeed,
    speech_instruction,
)
from app.workers.celery_app import celery_app
from app.workers.tasks import generate_audio_chunks


class FakeQwenModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_custom_voice(self, text: str, speaker: str, **kwargs: object):
        self.calls.append({"text": text, "speaker": speaker, **kwargs})
        return [[0.0, 0.1, -0.1]], 24_000


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


def test_qwen_is_loaded_lazily_and_uses_configured_voice() -> None:
    settings = get_settings().model_copy(update={"tts_voice": "Narrator"})
    loads = 0
    model = FakeQwenModel()

    def load_model(_settings: object) -> FakeQwenModel:
        nonlocal loads
        loads += 1
        return model

    tts = QwenTTSSynthesizer(settings, model_loader=load_model, wav_encoder=lambda *_: b"wav")
    assert loads == 0

    result = tts.synthesize(SpeechRequest(text="Тест"))
    tts.synthesize(SpeechRequest(text="Ещё тест"))

    assert result.content == b"wav"
    assert loads == 1
    assert model.calls[0]["speaker"] == "Narrator"
    assert "обычный" in str(model.calls[0]["instruct"])


def test_openai_tts_maps_existing_voice_and_returns_wav() -> None:
    client = FakeOpenAIClient(wav_bytes())
    settings = get_settings().model_copy(
        update={"tts_openai_model": "gpt-4o-mini-tts", "tts_openai_slow_speed": 0.8}
    )

    result = OpenAITTSSynthesizer(settings, client=client).synthesize(
        SpeechRequest(text="Тест", voice="Vivian", speed=SpeechSpeed.SLOW)
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
            SpeechRequest(text="Тест", voice="unsupported")
        )
    assert client.audio.speech.calls == []


def test_slow_mode_changes_the_speech_instruction() -> None:
    settings = get_settings()
    assert "медленнее" in speech_instruction(settings, SpeechSpeed.SLOW)
    assert "обычный" in speech_instruction(settings, SpeechSpeed.NORMAL)


def test_reading_style_changes_the_speech_instruction() -> None:
    settings = get_settings()

    assert "спокойную" in speech_instruction(settings, SpeechSpeed.NORMAL, ReadingStyle.CALM)
    assert "выразительной" in speech_instruction(
        settings, SpeechSpeed.NORMAL, ReadingStyle.EXPRESSIVE
    )


def test_tts_tasks_are_routed_to_a_dedicated_queue() -> None:
    route = celery_app.conf.task_routes["ai_reader.tts.*"]
    assert route["queue"] == "tts"


def test_chunk_generation_retries_only_retryable_failures() -> None:
    assert generate_audio_chunks.autoretry_for == (AudioChunkProcessingError,)
    assert generate_audio_chunks.retry_kwargs == {"max_retries": 2}
    assert generate_audio_chunks.retry_backoff is True


def test_empty_speech_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SpeechRequest(text="   ")
