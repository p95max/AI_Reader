from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the service liveness status."""
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    """Report ready only when the API can reach its durable database."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return HealthResponse(status="ok")
