# AI Reader

AI Reader turns uploaded PDF books into navigable audio. It extracts a book's
structure, adapts text for narration with an LLM, creates audio through OpenAI
TTS, and makes ready segments available while the rest of the book continues
processing in the background.

The interface and API are English-only.

## What is included

- Password-based accounts with isolated libraries, preferences, playback
  positions, and usage totals.
- PDF upload validation: PDF only, up to 100 MB and 500 pages by default.
- Auto-detected metadata (title, author, publication year) and reading-language
  selection.
- Page-range processing, pause, cancel, resume, and continuation-PDF support.
- Background PDF parsing, section detection, LLM narration, and resilient TTS
  jobs through Celery and Redis.
- Incremental playback with chapter navigation, playback-position persistence,
  a mini-player, volume, and speed controls.
- Per-book and global LLM/TTS usage, costs, and pre-processing estimates.
- A per-book TTS spending cap that retains ready audio and pauses before the
  next estimated segment would exceed the configured budget.

## Stack

Python 3.14, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Celery, Redis, MinIO,
OpenAI API, OpenAI `gpt-4o-mini-tts`, and a vanilla JavaScript SPA. Docker
Compose runs the complete local stack.

## Quick start with Docker

```bash
cp .env.example .env
# Set AI_READER_OPENAI_API_KEY in .env
docker compose up --build -d
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The OpenAPI reference is
at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Compose starts PostgreSQL, Redis, MinIO, migrations, the API, the PDF-processing
worker, and the TTS worker. Migrations run before the API and workers. The image
does not download or include PyTorch, CUDA, FlashAttention, Qwen, or a Hugging
Face model cache.

### Development account

In `local` and `development` environments, the migration container runs an
idempotent initializer that creates the following account:

```text
Email:    test@ai-reader.dev
Password: 1234
```

The sign-in form pre-fills these credentials only in those environments. The
initializer is disabled in staging and production. It also transfers the legacy
single-user library to this development account when upgrading an old local
installation.

### Development hot reload

`docker-compose.yml` is a development configuration. Source code and Alembic
migrations are mounted into containers: Uvicorn reloads the API, and the two
workers restart when Python files change. Rebuild only after changing a
dependency or the Dockerfile:

```bash
docker compose up --build -d
```

Useful commands:

```bash
docker compose ps
docker compose logs -f api worker-processing worker-tts
docker compose run --rm migrate
docker compose down
docker compose down -v # permanently removes local database, Redis, and object-storage data
```

## Configuration

Copy `.env.example` to `.env`. The important settings are:

| Variable | Purpose |
| --- | --- |
| `AI_READER_OPENAI_API_KEY` | Required for LLM narration and OpenAI TTS. |
| `AI_READER_AI_MODEL` | LLM used to adapt extracted content. |
| `AI_READER_AI_MODEL_PRICE_LIST` | Versioned JSON price list for LLM estimates and recorded usage. |
| `AI_READER_TTS_OPENAI_MODEL` | OpenAI TTS model; defaults to `gpt-4o-mini-tts`. |
| `AI_READER_TTS_OPENAI_VOICE` | Default OpenAI narrator voice. |
| `AI_READER_TTS_EXTERNAL_COST_PER_AUDIO_HOUR_USD` | Planning rate used for the audio estimate and TTS cost display. |
| `AI_READER_TTS_MAX_BOOK_COST_USD` | Pre-flight TTS spending cap per book; `0` disables it deliberately. |
| `AI_READER_AUTH_SECRET_KEY` | Unique secret required outside local development. |
| `AI_READER_AUTH_SESSION_HOURS` | Browser-session lifetime; defaults to 168 hours. |
| `AI_READER_AUTH_COOKIE_SECURE` | Set to `true` when serving HTTPS. |
| `APP_PORT` | Host port for the API and web interface; defaults to 8000. |

For staging and production, use a unique random auth secret, set
`AI_READER_AUTH_COOKIE_SECURE=true`, publish the service behind HTTPS, and keep
the development account disabled by setting `AI_READER_ENVIRONMENT=staging` or
`production`.

## Processing and cost behaviour

1. Upload a PDF and choose the narration language and initial page range.
2. AI Reader stores the PDF, extracts metadata, and shows a cost and duration
   estimate before processing begins.
3. A processing worker splits the selected pages into sections and narration
   chunks. An LLM adapts each chunk for listening.
4. A TTS worker creates WAV audio segments. Ready segments can be played before
   the remaining book completes.
5. The player and settings dashboard report progress, generated audio duration,
   LLM usage, and TTS cost.

OpenAI bills TTS by input text and output audio tokens. The audio-hour rate is
therefore a planning approximation, not an invoice. The pre-flight cap checks
the estimated next segment plus ready-audio cost; completed chunks are reused
and are not submitted again. Raise the cap and resume the book to continue.

External TTS is convenient but can be expensive for long books—roughly $1 per
generated audio hour at the default planning rate. A future local Qwen backend
is planned for deployments that can trade CPU/GPU resources for lower marginal
TTS cost. It is not part of the current build.

## Authentication and access control

`POST /api/v1/auth/register` creates an account and starts a browser session.
Registration requires a 2–80 character display name, a valid email, and a
12+ character password containing uppercase, lowercase, and numeric characters.
`POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`
manage the session. Passwords are hashed with Argon2 and sessions use an
HttpOnly, SameSite=Strict signed cookie.

All book and settings endpoints require a signed-in account. Queries and object
access are scoped to the account that owns the book; another account receives a
not-found response rather than another user's data.

## API overview

Health endpoints are public:

```text
GET  /api/v1/health
GET  /api/v1/health/ready
```

Core endpoints:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
GET    /api/v1/books
POST   /api/v1/books
DELETE /api/v1/books/{book_id}
POST   /api/v1/books/{book_id}/process
POST   /api/v1/books/{book_id}/pause
POST   /api/v1/books/{book_id}/cancel
GET    /api/v1/books/{book_id}/audio
GET    /api/v1/books/{book_id}/playback
PUT    /api/v1/books/{book_id}/playback
GET    /api/v1/books/usage-summary
GET    /api/v1/settings/preferences
PUT    /api/v1/settings/preferences
```

The book and settings routes require an authenticated session. Registration,
login, and logout establish or clear that session.

The full schema, including page-range estimates, book parts, progress, stream,
usage, and development-only credentials, is available at `/docs`.

## Run without Docker

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d postgres redis minio
uv run alembic upgrade head
uv run python -m app.scripts.seed_development_user
uv run uvicorn app.main:app --reload
```

Start workers in separate terminals:

```bash
uv run celery -A app.workers.celery_app worker -Q processing --loglevel=INFO
uv run celery -A app.workers.celery_app worker -Q tts --loglevel=INFO
```

## Validation commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
node --check app/web/assets/app.js
```

## Public-domain PDF sources for manual testing

No third-party books are stored in this repository. Download a file directly
from its Project Gutenberg book page for manual testing:

- [The Tell-Tale Heart — Edgar Allan Poe](https://www.gutenberg.org/ebooks/2148)
  (included in *The Works of Edgar Allan Poe — Volume 2*).
- [Philochristus: Memoirs of a Disciple of the Lord — Edwin Abbott Abbott](https://www.gutenberg.org/ebooks/48843).

Project Gutenberg identifies these works as public domain in the USA. Review
the licence embedded in a downloaded file and the applicable law before
redistributing it.

## Repository layout

```text
app/
  api/v1/routes/            # authentication, books, preferences, health
  core/                     # settings, logging, rate limiting, languages
  db/                       # SQLAlchemy engine and sessions
  models/                   # account, book, section, usage, and audio ORM models
  schemas/                  # request and response contracts
  scripts/                  # development-user seed and maintenance scripts
  services/
    ai/                     # LLM adaptation, cache, and visual narration
    audio/                  # OpenAI TTS, usage, chunk storage, retries
    books/                  # ownership, metadata, estimates, progress, usage
    documents/              # upload, PDF parsing, sections, processing plans
    infrastructure/         # S3-compatible storage
  web/                      # single-page web interface and assets
  workers/                  # Celery orchestration and background tasks
alembic/                    # PostgreSQL migrations
tests/                      # automated unit and API-surface tests
docker-compose.yml          # complete local development stack
```
