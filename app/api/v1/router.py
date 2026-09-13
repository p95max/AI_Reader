from fastapi import APIRouter

from app.api.v1.routes import books, health, preferences

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(books.router, prefix="/books", tags=["books"])
api_router.include_router(preferences.router, prefix="/settings", tags=["settings"])
