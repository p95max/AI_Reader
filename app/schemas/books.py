from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.reading_language import ReadingLanguage
from app.models.book import BookStatus
from app.models.chapter import ProcessingStatus
from app.services.ai.technical_narrator import CodeMode, DiagramMode, FormulaMode, TableMode
from app.services.audio.tts import ReadingStyle, SpeechSpeed


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str
    publication_year: int | None
    original_filename: str
    content_type: str
    size_bytes: int
    page_count: int
    processing_start_page: int
    processing_end_page: int
    processing_paused: bool
    status: BookStatus
    reading_language: ReadingLanguage
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
    publication_year: int | None
    status: BookStatus
    progress_percent: float


class BookProcessingEstimateRead(BaseModel):
    page_count: int
    start_page: int
    end_page: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_ai_cost_usd: float
    estimated_tts_cost_usd: float
    estimated_total_cost_usd: float
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


class BookUsageSummaryItemRead(BaseModel):
    id: UUID
    title: str
    status: BookStatus
    created_at: datetime
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    request_count: int
    ai_cost_usd: float
    tts_cost_usd: float
    total_cost_usd: float
    generated_audio_seconds: int


class BookUsageSummaryRead(BaseModel):
    total_books: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    request_count: int
    ai_cost_usd: float
    tts_cost_usd: float
    total_cost_usd: float
    generated_audio_seconds: int
    books: list[BookUsageSummaryItemRead]


class NarrationPreferences(BaseModel):
    reading_language: ReadingLanguage = ReadingLanguage.AUTO
    voice: str = Field(default="alloy", min_length=1, max_length=100)
    speed: SpeechSpeed = SpeechSpeed.NORMAL
    style: ReadingStyle = ReadingStyle.NEUTRAL
    code_mode: CodeMode = CodeMode.HYBRID
    table_mode: TableMode = TableMode.SUMMARIZE
    diagram_mode: DiagramMode = DiagramMode.DESCRIBE
    formula_mode: FormulaMode = FormulaMode.EXPLAIN


class BookTTSSettingsUpdate(NarrationPreferences):
    pass


class BookProcessingRequest(BookTTSSettingsUpdate):
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)


class BookPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    original_filename: str
    page_count: int
    global_start_page: int
    structure_built: bool


class UserPreferencesUpdate(NarrationPreferences):
    pass


class UserPreferencesRead(NarrationPreferences):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime


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
