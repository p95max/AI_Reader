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
uv run celery -A app.workers.celery_app worker --loglevel=INFO
```

`docker compose down` останавливает PostgreSQL и Redis, не удаляя их тома.

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
alembic/        # миграции PostgreSQL
docker-compose.yml
  main.py       # точка входа FastAPI
tests/          # тесты
```
