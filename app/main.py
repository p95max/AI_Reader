from pathlib import Path
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

settings = get_settings()
configure_logging(debug=settings.debug)
WEB_ROOT = Path(__file__).parent / "web"
logger = structlog.get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(api_router, prefix="/api/v1")
app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")


@app.middleware("http")
async def log_request(request, call_next):
    """Emit one structured event per request without recording user content."""
    request_id = request.headers.get("x-request-id") or str(uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed",
            method=request.method,
            path=request.url.path,
            duration_ms=round((perf_counter() - started_at) * 1_000),
        )
        raise
    else:
        response.headers["x-request-id"] = request_id
        logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started_at) * 1_000),
        )
        return response
    finally:
        structlog.contextvars.clear_contextvars()


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
