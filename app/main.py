from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
