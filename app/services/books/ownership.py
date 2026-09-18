"""Ownership checks shared by authenticated book endpoints."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_owned_book(session: AsyncSession, book_id: UUID, user_id: UUID):
    """Return a book only when it belongs to the signed-in user."""
    from app.models.book import Book

    return await session.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
