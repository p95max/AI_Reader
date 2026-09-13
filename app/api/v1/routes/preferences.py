from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.books import UserPreferencesRead, UserPreferencesUpdate
from app.services.user_preferences import get_or_create_user_preferences

router = APIRouter()


@router.get("/preferences", response_model=UserPreferencesRead)
async def get_preferences(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserPreferencesRead:
    """Return the local user's defaults for future book processing."""
    preferences = await get_or_create_user_preferences(session)
    await session.commit()
    await session.refresh(preferences)
    return UserPreferencesRead.model_validate(preferences)


@router.put("/preferences", response_model=UserPreferencesRead)
async def update_preferences(
    payload: UserPreferencesUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserPreferencesRead:
    """Save defaults; each book copies them when its processing starts."""
    preferences = await get_or_create_user_preferences(session)
    for field, value in payload.model_dump().items():
        setattr(preferences, field, getattr(value, "value", value))
    await session.commit()
    await session.refresh(preferences)
    return UserPreferencesRead.model_validate(preferences)
