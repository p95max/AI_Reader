import io
import struct
import wave
from uuid import UUID

import pytest

from app.services.audio.audio_generation import (
    AudioChunkGenerator,
    NarrationChunker,
    wav_duration_milliseconds,
)
from app.services.audio.tts import AudioResult, SpeechRequest


def wav_bytes(*, sample_rate: int = 1_000, frames: int = 1_500) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


class FakeSynthesizer:
    provider_name = "openai"
    model_name = "gpt-4o-mini-tts"

    def __init__(self) -> None:
        self.requests: list[SpeechRequest] = []

    def synthesize(self, request: SpeechRequest) -> AudioResult:
        self.requests.append(request)
        return AudioResult(content=wav_bytes(), sample_rate=1_000)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def upload_bytes(self, content: bytes, key: str, content_type: str) -> None:
        self.objects[key] = (content, content_type)


def test_chunker_prefers_sentence_boundaries_and_never_exceeds_limit() -> None:
    chunker = NarrationChunker(max_characters=25)
    chunks = chunker.split("First sentence. Second sentence. Third sentence.")

    assert chunks == ["First sentence.", "Second sentence.", "Third sentence."]
    assert all(len(chunk) <= 25 for chunk in chunks)


def test_chunker_splits_a_long_sentence_at_word_boundaries() -> None:
    chunker = NarrationChunker(max_characters=100)
    chunks = chunker.split("word " * 80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert all(not chunk.startswith(" ") and not chunk.endswith(" ") for chunk in chunks)


def test_generator_saves_wav_and_duration_for_every_chunk() -> None:
    synthesizer = FakeSynthesizer()
    storage = MemoryStorage()
    generator = AudioChunkGenerator(
        synthesizer, storage, chunker=NarrationChunker(max_characters=25)
    )
    book_id = UUID("12345678-1234-5678-1234-567812345678")

    chunks = generator.generate(book_id, "First sentence. Second sentence.")

    assert [chunk.duration_milliseconds for chunk in chunks] == [1_500, 1_500]
    assert [chunk.storage_key for chunk in chunks] == [
        "books/12345678-1234-5678-1234-567812345678/audio/000000.wav",
        "books/12345678-1234-5678-1234-567812345678/audio/000001.wav",
    ]
    assert list(storage.objects) == [chunk.storage_key for chunk in chunks]
    assert {(chunk.tts_provider, chunk.tts_model) for chunk in chunks} == {
        ("openai", "gpt-4o-mini-tts")
    }
    assert len(synthesizer.requests) == 2


def test_wav_duration_rejects_invalid_content() -> None:
    with pytest.raises(ValueError, match="invalid WAV"):
        wav_duration_milliseconds(b"not-a-wav")


def test_wav_duration_uses_available_bytes_when_data_header_is_invalid() -> None:
    content = bytearray(wav_bytes(sample_rate=1_000, frames=1_500))
    struct.pack_into("<I", content, 40, 2_147_483_647)

    assert wav_duration_milliseconds(bytes(content)) == 1_500
