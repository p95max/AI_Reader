"""Create the predictable local-development account after migrations."""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services.authentication import claim_legacy_local_library, hash_password

DEVELOPMENT_EMAIL = "test@ai-reader.dev"
PREVIOUS_DEVELOPMENT_EMAIL = "test@ai-reader.local"
DEVELOPMENT_PASSWORD = "1234"
DEVELOPMENT_DISPLAY_NAME = "Test"


async def seed_development_user() -> None:
    """Create or repair the development account without touching non-dev data."""
    if get_settings().environment not in {"local", "development"}:
        return
    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.email.in_((DEVELOPMENT_EMAIL, PREVIOUS_DEVELOPMENT_EMAIL)))
        )
        if user is None:
            user = User(
                email=DEVELOPMENT_EMAIL,
                display_name=DEVELOPMENT_DISPLAY_NAME,
            )
            session.add(user)
            await session.flush()
        # This account is development-only, so every init run intentionally
        # restores the documented deterministic credentials.
        user.email = DEVELOPMENT_EMAIL
        user.display_name = DEVELOPMENT_DISPLAY_NAME
        user.password_hash = hash_password(DEVELOPMENT_PASSWORD)
        await claim_legacy_local_library(session, user)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_development_user())
