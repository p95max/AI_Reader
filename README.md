# AI Reader API

Backend-сервис AI Reader на FastAPI и Python 3.14.

## Быстрый старт

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Сервис будет доступен на `http://127.0.0.1:8000`.
Интерактивная спецификация API: `http://127.0.0.1:8000/docs`.

В отдельном терминале запустите worker задач:

```bash
uv run celery -A app.workers.celery_app worker -Q processing --loglevel=INFO
```

TTS использует отдельную очередь и воркер (первый синтез загрузит модель, заданную
`AI_READER_TTS_MODEL`):

```bash
uv run celery -A app.workers.celery_app worker -Q tts --loglevel=INFO
```

По умолчанию выбран Qwen3-TTS 1.7B. Провайдер, модель, голос, язык и базовая
инструкция задаются переменными `AI_READER_TTS_*`; задача и остальной код не
привязаны к Qwen, поэтому новый провайдер подключается через адаптер TTS.

`docker compose down` останавливает PostgreSQL, Redis и MinIO, не удаляя их тома.
MinIO (S3-совместимое хранилище) доступно на `http://127.0.0.1:9001`.

## Команды разработки

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Структура

```text
app/
  api/v1/       # HTTP-эндпоинты и схемы API
  core/         # конфигурация приложения
  db/           # SQLAlchemy engine, сессии и metadata
  workers/      # Celery application и фоновые задачи
  models/        # ORM-модели
  services/      # S3-хранилище и обработка upload
alembic/        # миграции PostgreSQL
docker-compose.yml
  main.py       # точка входа FastAPI
tests/          # тесты
```
