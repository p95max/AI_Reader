"""Temporary single-user ownership bridge until the Auth MVP stage is implemented."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

LOCAL_USER_EMAIL = "local@ai-reader.invalid"


async def get_local_user_id(session: AsyncSession) -> UUID:
    """Return the seeded MVP owner, recovering safely if a database was created manually."""
    user = await session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
    if user is None:
        user = User(email=LOCAL_USER_EMAIL)
        session.add(user)
        await session.flush()
    return user.id
