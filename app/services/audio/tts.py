"""OpenAI text-to-speech boundary used by the background TTS worker."""

from __future__ import annotations

import base64
import io
import wave
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol

from openai import OpenAI

from app.core.config import Settings, get_settings


class TTSError(RuntimeError):
    """Raised when a configured TTS provider cannot synthesize speech."""


class SpeechSpeed(StrEnum):
    NORMAL = "normal"
    SLOW = "slow"


class ReadingStyle(StrEnum):
    NEUTRAL = "neutral"
    CALM = "calm"
    EXPRESSIVE = "expressive"


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    text: str
    voice: str | None = None
    speed: SpeechSpeed = SpeechSpeed.NORMAL
    style: ReadingStyle = ReadingStyle.NEUTRAL

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Speech text must not be empty")


@dataclass(frozen=True, slots=True)
class AudioResult:
    content: bytes
    sample_rate: int
    mime_type: str = "audio/wav"

    def as_task_payload(self) -> dict[str, str | int]:
        """Temporary worker payload; object storage is added in TTS stage 5.2."""
        return {
            "audio_base64": base64.b64encode(self.content).decode("ascii"),
            "mime_type": self.mime_type,
            "sample_rate": self.sample_rate,
        }


class SpeechSynthesizer(Protocol):
    def synthesize(self, request: SpeechRequest) -> AudioResult: ...


class OpenAITextToSpeechClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class OpenAIAudioClient(Protocol):
    speech: OpenAITextToSpeechClient


class OpenAITTSClient(Protocol):
    audio: OpenAIAudioClient


def speech_instruction(
    settings: Settings,
    speed: SpeechSpeed,
    style: ReadingStyle = ReadingStyle.NEUTRAL,
) -> str:
    pace = {
        SpeechSpeed.NORMAL: "Используй обычный, естественный темп речи.",
        SpeechSpeed.SLOW: "Говори медленнее обычного, чётко выделяя смысловые паузы.",
    }[speed]
    delivery = {
        ReadingStyle.NEUTRAL: "Сохраняй нейтральную, информативную подачу.",
        ReadingStyle.CALM: "Используй спокойную, мягкую подачу без излишней экспрессии.",
        ReadingStyle.EXPRESSIVE: "Подчёркивай важные мысли естественной выразительной интонацией.",
    }[style]
    return f"{settings.tts_instruction.strip()} {pace} {delivery}"


OPENAI_TTS_VOICES = frozenset(
    {
        "alloy", "ash", "ballad", "cedar", "coral", "echo", "fable", "marin",
        "nova", "onyx", "sage", "shimmer", "verse",
    }
)
_LEGACY_OPENAI_VOICE_MAP = {"ryan": "onyx", "aiden": "echo", "vivian": "nova"}


class OpenAITTSSynthesizer:
    """OpenAI TTS adapter returning WAV audio for storage and playback."""

    provider_name = "openai"

    def __init__(self, settings: Settings, *, client: OpenAITTSClient | None = None) -> None:
        self._settings = settings
        if client is None:
            api_key = settings.openai_api_key
            if api_key is None:
                raise TTSError("AI_READER_OPENAI_API_KEY must be configured for OpenAI TTS")
            client = OpenAI(
                api_key=api_key.get_secret_value(), timeout=settings.tts_openai_timeout_seconds
            )
        self._client = client

    def synthesize(self, request: SpeechRequest) -> AudioResult:
        try:
            response = self._client.audio.speech.create(
                model=self._settings.tts_openai_model,
                voice=self._voice(request.voice),
                input=request.text,
                instructions=speech_instruction(self._settings, request.speed, request.style),
                response_format="wav",
                speed=self._speed(request.speed),
            )
            content = bytes(response.content)
            return AudioResult(
                content=content,
                sample_rate=_wav_sample_rate(content),
                mime_type="audio/wav",
            )
        except TTSError:
            raise
        except Exception as error:
            raise TTSError(f"OpenAI TTS synthesis failed: {error}") from error

    def _voice(self, requested_voice: str | None) -> str:
        candidate = (requested_voice or self._settings.tts_openai_voice).strip().lower()
        candidate = _LEGACY_OPENAI_VOICE_MAP.get(candidate, candidate)
        if candidate not in OPENAI_TTS_VOICES:
            available = ", ".join(sorted(OPENAI_TTS_VOICES))
            raise TTSError(f"Unknown OpenAI TTS voice '{candidate}'. Available: {available}")
        return candidate

    def _speed(self, speed: SpeechSpeed) -> float:
        return (
            self._settings.tts_openai_slow_speed
            if speed == SpeechSpeed.SLOW
            else self._settings.tts_openai_normal_speed
        )

    @property
    def model_name(self) -> str:
        return self._settings.tts_openai_model


@lru_cache
def get_tts_synthesizer() -> SpeechSynthesizer:
    """Return the one supported synthesizer for this deployment."""
    return OpenAITTSSynthesizer(get_settings())


def _wav_sample_rate(content: bytes) -> int:
    try:
        with wave.open(io.BytesIO(content)) as wav_file:
            sample_rate = wav_file.getframerate()
    except (EOFError, wave.Error) as error:
        raise TTSError("OpenAI TTS returned invalid WAV audio") from error
    if sample_rate <= 0:
        raise TTSError("OpenAI TTS returned a WAV file without a sample rate")
    return sample_rate
