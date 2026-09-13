# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.7.12 AS uv

FROM python:3.14-slim AS base

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS tts-cpu
RUN uv sync --frozen --no-dev --extra tts-cpu --no-install-project
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "tts", "--loglevel=INFO"]

FROM base AS tts-gpu
RUN uv sync --frozen --no-dev --extra tts-gpu --no-install-project
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "tts", "--loglevel=INFO"]
