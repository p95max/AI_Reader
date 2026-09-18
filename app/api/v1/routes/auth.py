"""Browser-session registration and sign-in endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RegistrationRequest, UserRead
from app.services.authentication import (
    SESSION_COOKIE_NAME,
    claim_legacy_local_library,
    create_session_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user, settings),
        max_age=settings.auth_session_hours * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    email = str(payload.email).lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email",
        )
    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()
    await claim_legacy_local_library(session, user)
    await session.commit()
    await session.refresh(user)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=get_settings().auth_cookie_secure,
        samesite="strict",
    )
    return response


@router.get("/me", response_model=UserRead)
async def me(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    return await get_current_user(request, session)
