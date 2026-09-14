"""Extensible text-to-speech boundary.

Callers know only :class:`SpeechSynthesizer`.  Provider-specific loading and
audio encoding live behind adapters, so moving from Qwen to another service
does not affect task payloads or the worker contract.
"""

from __future__ import annotations

import base64
import io
import wave
from collections.abc import Callable
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


class QwenModel(Protocol):
    def generate_custom_voice(
        self,
        text: str,
        speaker: str,
        language: str | None = None,
        instruct: str | None = None,
        **kwargs: Any,
    ) -> tuple[list[Any], int]: ...


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


class QwenTTSSynthesizer:
    """Qwen3-TTS adapter with lazy model initialisation."""

    def __init__(
        self,
        settings: Settings,
        *,
        model_loader: Callable[[Settings], QwenModel] | None = None,
        wav_encoder: Callable[[Any, int], bytes] | None = None,
    ) -> None:
        self._settings = settings
        self._model_loader = model_loader or _load_qwen_model
        self._wav_encoder = wav_encoder or _encode_wav
        self._model: QwenModel | None = None

    def synthesize(self, request: SpeechRequest) -> AudioResult:
        model = self._model or self._load_model()
        waveforms, sample_rate = model.generate_custom_voice(
            request.text,
            speaker=request.voice or self._settings.tts_voice,
            language=self._settings.tts_language,
            instruct=speech_instruction(self._settings, request.speed, request.style),
            non_streaming_mode=True,
        )
        if not waveforms:
            raise TTSError("Qwen returned no audio")
        return AudioResult(
            content=self._wav_encoder(waveforms[0], sample_rate),
            sample_rate=sample_rate,
        )

    def _load_model(self) -> QwenModel:
        self._model = self._model_loader(self._settings)
        return self._model


OPENAI_TTS_VOICES = frozenset(
    {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}
)
_LEGACY_OPENAI_VOICE_MAP = {"ryan": "onyx", "aiden": "echo", "vivian": "nova"}


class OpenAITTSSynthesizer:
    """OpenAI TTS adapter returning the same WAV result as the local provider."""

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


ProviderFactory = Callable[[Settings], SpeechSynthesizer]
_PROVIDERS: dict[str, ProviderFactory] = {
    "qwen": QwenTTSSynthesizer,
    "openai": OpenAITTSSynthesizer,
}


def register_tts_provider(name: str, factory: ProviderFactory) -> None:
    """Register an adapter, for example at application startup or in a plugin."""
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("TTS provider name must not be empty")
    _PROVIDERS[normalized_name] = factory
    get_tts_synthesizer.cache_clear()


@lru_cache
def get_tts_synthesizer() -> SpeechSynthesizer:
    settings = get_settings()
    provider_name = settings.tts_provider.strip().lower()
    try:
        factory = _PROVIDERS[provider_name]
    except KeyError as error:
        available = ", ".join(sorted(_PROVIDERS))
        raise TTSError(f"Unknown TTS provider '{provider_name}'. Available: {available}") from error
    return factory(settings)


def _load_qwen_model(settings: Settings) -> QwenModel:
    try:
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as error:  # pragma: no cover - environment setup branch
        raise TTSError("Qwen TTS dependencies are not installed") from error

    dtype = torch.bfloat16 if settings.tts_device == "cuda" else torch.float32
    return Qwen3TTSModel.from_pretrained(
        settings.tts_model,
        device_map=settings.tts_device,
        dtype=dtype,
    )


def _encode_wav(waveform: Any, sample_rate: int) -> bytes:
    try:
        import soundfile as sf
    except ImportError as error:  # pragma: no cover - supplied by qwen-tts
        raise TTSError("soundfile is required to encode TTS audio") from error

    output = io.BytesIO()
    sf.write(output, waveform, sample_rate, format="WAV")
    return output.getvalue()


def _wav_sample_rate(content: bytes) -> int:
    try:
        with wave.open(io.BytesIO(content)) as wav_file:
            sample_rate = wav_file.getframerate()
    except (EOFError, wave.Error) as error:
        raise TTSError("OpenAI TTS returned invalid WAV audio") from error
    if sample_rate <= 0:
        raise TTSError("OpenAI TTS returned a WAV file without a sample rate")
    return sample_rate
