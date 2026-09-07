from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.book import BookStatus


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
