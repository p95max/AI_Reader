from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.book import BookStatus
from app.models.chapter import ProcessingStatus


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: BookStatus
    created_at: datetime
    updated_at: datetime


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
