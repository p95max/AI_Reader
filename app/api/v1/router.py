from fastapi import APIRouter, Depends

from app.api.v1.routes import auth, books, health, preferences
from app.services.authentication import get_current_user

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    books.router,
    prefix="/books",
    tags=["books"],
    dependencies=[Depends(get_current_user)],
)
api_router.include_router(
    preferences.router,
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)
