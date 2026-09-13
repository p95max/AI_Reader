from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.book import BookStatus
from app.models.chapter import ProcessingStatus
from app.services.technical_narrator import CodeMode, DiagramMode, FormulaMode, TableMode
from app.services.tts import ReadingStyle, SpeechSpeed


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: BookStatus
    tts_voice: str
    tts_speed: SpeechSpeed
    tts_style: ReadingStyle
    code_mode: CodeMode
    table_mode: TableMode
    diagram_mode: DiagramMode
    formula_mode: FormulaMode
    created_at: datetime
    updated_at: datetime


class BookLibraryItemRead(BaseModel):
    id: UUID
    title: str
    author: str
    status: BookStatus
    progress_percent: float


class BookProcessingEstimateRead(BaseModel):
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_ai_cost_usd: float
    estimated_audio_seconds: int
    model_name: str
    pricing_version: str


class BookCostRead(BaseModel):
    estimated_cost_usd: float
    actual_cost_usd: float
    difference_usd: float
    actual_input_tokens: int
    actual_cached_input_tokens: int
    actual_output_tokens: int
    request_count: int
    estimate_model_name: str
    estimate_pricing_version: str
    actual_tts_cost_usd: float
    generated_audio_seconds: int
    tts_generation_seconds: int
    total_processing_cost_usd: float


class BookTTSSettingsUpdate(BaseModel):
    voice: str = Field(default="Ryan", min_length=1, max_length=100)
    speed: SpeechSpeed = SpeechSpeed.NORMAL
    style: ReadingStyle = ReadingStyle.NEUTRAL
    code_mode: CodeMode = CodeMode.HYBRID
    table_mode: TableMode = TableMode.SUMMARIZE
    diagram_mode: DiagramMode = DiagramMode.DESCRIBE
    formula_mode: FormulaMode = FormulaMode.EXPLAIN


class BookAudioChunkRead(BaseModel):
    id: UUID
    chunk_index: int
    duration_milliseconds: int
    content_type: str
    stream_url: str


class PlaybackPositionRead(BaseModel):
    book_id: UUID
    audio_chunk_id: UUID | None
    position_milliseconds: int
    updated_at: datetime | None


class PlaybackPositionUpdate(BaseModel):
    audio_chunk_id: UUID
    position_milliseconds: int = Field(ge=0)


class ContentChunkProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    page_number: int
    kind: str
    status: ProcessingStatus


class ChapterProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_index: int
    title: str
    start_page: int
    end_page: int
    status: ProcessingStatus
    total_chunks: int
    ready_chunks: int
    progress_percent: float
    chunks: tuple[ContentChunkProgressRead, ...]


class BookProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book_id: UUID
    status: ProcessingStatus
    total_chapters: int
    ready_chapters: int
    total_chunks: int
    queued_chunks: int
    processing_chunks: int
    ready_chunks: int
    failed_chunks: int
    progress_percent: float
    chapters: tuple[ChapterProgressRead, ...]
