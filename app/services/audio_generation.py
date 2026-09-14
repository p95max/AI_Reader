"""Chunk narration, synthesize it, and persist the audio payloads safely."""

from __future__ import annotations

import io
import re
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from app.services.storage import ObjectStorage
from app.services.tts import ReadingStyle, SpeechRequest, SpeechSpeed, SpeechSynthesizer

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True, slots=True)
class NarrationChunker:
    """Split narration at sentence or word boundaries without losing text."""

    max_characters: int = 1_200

    def __post_init__(self) -> None:
        if self.max_characters < 20:
            raise ValueError("max_characters must be at least 20")

    def split(self, narration: str) -> list[str]:
        normalized = " ".join(narration.split())
        if not normalized:
            return []

        chunks: list[str] = []
        current = ""
        for sentence in _SENTENCE_BOUNDARY.split(normalized):
            for part in self._split_long_text(sentence):
                if not current:
                    current = part
                elif len(current) + 1 + len(part) <= self.max_characters:
                    current = f"{current} {part}"
                else:
                    chunks.append(current)
                    current = part
        if current:
            chunks.append(current)
        return chunks

    def _split_long_text(self, text: str) -> Iterable[str]:
        text = text.strip()
        while len(text) > self.max_characters:
            split_at = text.rfind(" ", 0, self.max_characters + 1)
            if split_at <= 0:
                split_at = self.max_characters
            yield text[:split_at].strip()
            text = text[split_at:].strip()
        if text:
            yield text


@dataclass(frozen=True, slots=True)
class GeneratedAudioChunk:
    chunk_index: int
    narration: str
    storage_key: str
    content_type: str
    duration_milliseconds: int
    tts_provider: str | None = None
    tts_model: str | None = None

    def as_task_payload(self) -> dict[str, str | int]:
        return {
            "chunk_index": self.chunk_index,
            "storage_key": self.storage_key,
            "content_type": self.content_type,
            "duration_milliseconds": self.duration_milliseconds,
        }


class AudioChunkGenerator:
    """Connects provider-neutral TTS to object storage for one book."""

    def __init__(
        self,
        synthesizer: SpeechSynthesizer,
        storage: ObjectStorage,
        *,
        chunker: NarrationChunker | None = None,
    ) -> None:
        self._synthesizer = synthesizer
        self._storage = storage
        self._chunker = chunker or NarrationChunker()

    def generate(
        self,
        book_id: UUID,
        narration: str,
        *,
        voice: str | None = None,
        speed: SpeechSpeed = SpeechSpeed.NORMAL,
        style: ReadingStyle = ReadingStyle.NEUTRAL,
    ) -> list[GeneratedAudioChunk]:
        generated: list[GeneratedAudioChunk] = []
        for chunk_index, text in enumerate(self._chunker.split(narration)):
            generated.append(
                self.generate_chunk(
                    book_id,
                    chunk_index,
                    text,
                    voice=voice,
                    speed=speed,
                    style=style,
                )
            )
        return generated

    def split_narration(self, narration: str) -> list[str]:
        return self._chunker.split(narration)

    @property
    def tts_provider(self) -> str:
        return str(getattr(self._synthesizer, "provider_name", "openai"))

    @property
    def tts_model(self) -> str | None:
        model = getattr(self._synthesizer, "model_name", None)
        return str(model) if model is not None else None

    def generate_chunk(
        self,
        book_id: UUID,
        chunk_index: int,
        narration: str,
        *,
        voice: str | None = None,
        speed: SpeechSpeed = SpeechSpeed.NORMAL,
        style: ReadingStyle = ReadingStyle.NEUTRAL,
    ) -> GeneratedAudioChunk:
        audio = self._synthesizer.synthesize(
            SpeechRequest(text=narration, voice=voice, speed=speed, style=style)
        )
        storage_key = audio_storage_key(book_id, chunk_index)
        self._storage.upload_bytes(audio.content, storage_key, audio.mime_type)
        return GeneratedAudioChunk(
            chunk_index=chunk_index,
            narration=narration,
            storage_key=storage_key,
            content_type=audio.mime_type,
            duration_milliseconds=wav_duration_milliseconds(audio.content),
            tts_provider=self.tts_provider,
            tts_model=self.tts_model,
        )


def audio_storage_key(book_id: UUID, chunk_index: int) -> str:
    if chunk_index < 0:
        raise ValueError("chunk_index must not be negative")
    return f"books/{book_id}/audio/{chunk_index:06d}.wav"


def wav_duration_milliseconds(content: bytes) -> int:
    """Read WAV duration from the generated bytes; no provider assumptions needed."""
    try:
        with wave.open(io.BytesIO(content)) as wav_file:
            if wav_file.getframerate() <= 0:
                raise ValueError("WAV sample rate must be positive")
            return round(wav_file.getnframes() / wav_file.getframerate() * 1_000)
    except (EOFError, wave.Error) as error:
        raise ValueError("TTS provider returned invalid WAV audio") from error
