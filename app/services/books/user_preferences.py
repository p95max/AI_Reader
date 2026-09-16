"""Read and apply durable narration preferences for the local MVP user."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.book import Book
from app.models.user_preferences import UserPreferences
from app.schemas.books import NarrationPreferences
from app.services.books.ownership import get_local_user_id


async def get_or_create_user_preferences(
    session: AsyncSession, settings: Settings | None = None
) -> UserPreferences:
    user_id = await get_local_user_id(session)
    preferences = await session.get(UserPreferences, user_id)
    if preferences is None:
        settings = settings or get_settings()
        preferences = UserPreferences(user_id=user_id, voice=settings.tts_voice)
        session.add(preferences)
        await session.flush()
    return preferences


def _plain_value(value: object) -> str:
    return str(getattr(value, "value", value))


def apply_preferences_to_book(
    book: Book, preferences: NarrationPreferences | UserPreferences
) -> None:
    """Persist an immutable processing snapshot on the book."""
    book.tts_voice = preferences.voice
    book.tts_speed = _plain_value(preferences.speed)
    book.tts_style = _plain_value(preferences.style)
    book.code_mode = _plain_value(preferences.code_mode)
    book.table_mode = _plain_value(preferences.table_mode)
    book.diagram_mode = _plain_value(preferences.diagram_mode)
    book.formula_mode = _plain_value(preferences.formula_mode)
