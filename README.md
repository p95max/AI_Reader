# AI Reader API

AI Reader is a FastAPI service for turning PDF books into narrated audio. It
uses Python 3.14, PostgreSQL, Redis, MinIO, Celery, and OpenAI TTS.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Compose starts PostgreSQL, Redis, MinIO, Alembic migrations, FastAPI, a PDF
processing worker, and an OpenAI TTS worker. Migrations run before the API and
workers start. The image does not include local TTS models, PyTorch, CUDA, or a
Hugging Face model cache.

Open `http://127.0.0.1:8000` (or the configured `APP_PORT`). API documentation
is available at `http://127.0.0.1:8000/docs`.

Useful commands:

```bash
docker compose logs -f
docker compose run --rm migrate
docker compose down
docker compose down -v # remove all local service data
```

`docker-compose.yml` is the development configuration. Python code and Alembic
migrations are mounted into containers: Uvicorn reloads the API after Python
changes, and the processing and TTS workers restart when Python code changes.
Rebuild only after changing `pyproject.toml`, `uv.lock`, or `Dockerfile`:

```bash
docker compose up --build -d
```

## OpenAI TTS and cost estimates

The default synthesis model is OpenAI `gpt-4o-mini-tts`. Set
`AI_READER_OPENAI_API_KEY`, then optionally adjust
`AI_READER_TTS_OPENAI_MODEL`, the default voice, and the narration instruction.
The TTS worker performs at most two concurrent requests
(`AI_READER_TTS_WORKER_CONCURRENCY`).

### Current cost limitation and planned local TTS

External TTS is convenient and fast to operate, but it is currently expensive
for long books: the planning rate is close to **$1 per generated audio hour**.
That makes full-book narration costly even when LLM processing costs are low.

The next planned TTS backend is a local Qwen model. It will be offered as an
alternative to OpenAI TTS so that deployments with suitable hardware can trade
GPU/CPU capacity for a substantially lower marginal cost. The current Docker
image intentionally remains external-TTS-only; it does not download or bundle
Qwen yet.

The upload UI returns an approximate pre-processing total. It includes the LLM
estimate and an estimated TTS cost based on
`AI_READER_TTS_EXTERNAL_COST_PER_AUDIO_HOUR_USD`. OpenAI bills TTS by text and
audio tokens, so the audio-hour value is only a planning approximation. Actual
costs are recorded during processing at `GET /api/v1/books/{book_id}/cost`.

The versioned LLM price list is configured in
`AI_READER_AI_MODEL_PRICE_LIST`, with USD prices per one million tokens:

```bash
AI_READER_AI_MODEL_PRICE_LIST='{"gpt-5.6-luna":{"input_per_million_tokens":2.0,"cached_input_per_million_tokens":0.5,"output_per_million_tokens":8.0,"version":"2026-09"}}'
```

When a model has no entry, the compatible
`AI_READER_AI_*_COST_PER_MILLION_TOKENS` and `AI_READER_AI_PRICING_VERSION`
variables are used instead.

PostgreSQL, Redis, and MinIO are available only inside the Docker network. Use
`docker compose exec` for diagnostics; data is stored in named volumes.

## Run locally without Docker

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d postgres redis minio
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In separate terminals, start workers when needed:

```bash
uv run celery -A app.workers.celery_app worker -Q processing --loglevel=INFO
uv run celery -A app.workers.celery_app worker -Q tts --loglevel=INFO
```

## Development commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Repository structure

```text
app/
  api/v1/                   # HTTP endpoints
  core/                     # configuration, logging, rate limits
  db/                       # SQLAlchemy engine, sessions, metadata
  models/                   # ORM entities
  schemas/                  # HTTP request/response schemas
  services/
    ai/                     # LLM adaptation, narration cache, visual narration
    audio/                  # TTS adapter, audio chunks, resilient generation
    books/                  # library, metadata, cost, usage, preferences
    documents/              # PDF parsing, structure, processing plans, uploads
    infrastructure/         # S3-compatible object storage
  workers/                  # Celery application and background orchestration
  web/                      # SPA shell and frontend assets
alembic/                    # PostgreSQL migrations
docker-compose.yml
tests/                      # automated tests
```
