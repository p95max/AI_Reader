from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()
WEB_ROOT = Path(__file__).parent / "web"

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)
app.include_router(api_router, prefix="/api/v1")
app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/library", status_code=307)


@app.get("/library", include_in_schema=False)
@app.get("/upload", include_in_schema=False)
@app.get("/player", include_in_schema=False)
@app.get("/settings", include_in_schema=False)
@app.get("/books/{book_id}", include_in_schema=False)
async def frontend_page() -> FileResponse:
    """Serve the SPA for every public application route, including deep links."""
    return FileResponse(WEB_ROOT / "index.html")
