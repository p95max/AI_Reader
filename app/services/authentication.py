"""Password hashing and signed browser-session helpers."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User

LEGACY_LOCAL_USER_EMAIL = "local@ai-reader.invalid"

SESSION_COOKIE_NAME = "ai_reader_session"
PASSWORD_HASHER = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return password_hash is not None and PASSWORD_HASHER.verify(password, password_hash)


def create_session_token(user: User, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.auth_session_hours)
    return jwt.encode(
        {"sub": str(user.id), "exp": expires_at, "type": "browser-session"},
        settings.auth_secret_key.get_secret_value(),
        algorithm="HS256",
    )


async def claim_legacy_local_library(session: AsyncSession, user: User) -> None:
    """Move pre-auth local data to the first account in a local installation."""
    if get_settings().environment not in {"local", "development"}:
        return
    legacy_user = await session.scalar(
        select(User).where(User.email == LEGACY_LOCAL_USER_EMAIL, User.password_hash.is_(None))
    )
    if legacy_user is None:
        return

    from app.models.book import Book
    from app.models.llm_usage import LLMUsageRecord
    from app.models.user_preferences import UserPreferences

    await session.execute(
        update(Book).where(Book.user_id == legacy_user.id).values(user_id=user.id)
    )
    await session.execute(
        update(LLMUsageRecord)
        .where(LLMUsageRecord.user_id == legacy_user.id)
        .values(user_id=user.id)
    )
    preferences = await session.get(UserPreferences, legacy_user.id)
    if preferences is not None:
        preferences.user_id = user.id


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required")
    try:
        payload = jwt.decode(
            token,
            get_settings().auth_secret_key.get_secret_value(),
            algorithms=["HS256"],
        )
        if payload.get("type") != "browser-session":
            raise jwt.InvalidTokenError("Invalid session type")
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError, jwt.PyJWTError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid",
        ) from error
    user = await session.get(User, user_id)
    if user is None or user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")
    return user
