# AI Reader API

Backend-сервис AI Reader на FastAPI и Python 3.14.

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Compose поднимает PostgreSQL, Redis, MinIO, миграции Alembic, FastAPI и два
Celery worker (обработка PDF и внешний OpenAI TTS). Миграции применяются до
старта API и worker автоматически. Все Python-сервисы используют один компактный
образ: локальные TTS-модели, PyTorch, CUDA и кеш Hugging Face не устанавливаются.

Сервис будет доступен на `http://127.0.0.1:8000` (или на значении `APP_PORT`).
Интерактивная спецификация API: `http://127.0.0.1:8000/docs`.

Логи всех компонентов:

```bash
docker compose logs -f
```

Если стек уже был запущен до добавления новой Alembic-миграции, примените её без
перезапуска данных:

```bash
docker compose run --rm migrate
```

Остановить стек, сохранив данные:

```bash
docker compose down
```

Для полного сброса данных:

```bash
docker compose down -v
```

### Live reload

`docker-compose.yml` является dev-конфигурацией. Python-исходники и миграции
монтируются в контейнеры: FastAPI перезагружается через Uvicorn при сохранении
файла, а processing- и TTS-worker автоматически перезапускаются при изменении
Python-кода. Пересборка нужна только после изменений `pyproject.toml`, `uv.lock`
или `Dockerfile`:

```bash
docker compose up --build -d
```

По умолчанию используется внешний OpenAI TTS `gpt-4o-mini-tts`. Задайте
`AI_READER_OPENAI_API_KEY`, при необходимости измените
`AI_READER_TTS_OPENAI_MODEL`, голос и инструкцию. TTS-worker выполняет не более
двух запросов одновременно (`AI_READER_TTS_WORKER_CONCURRENCY`), что можно
снизить при ограниченном API-тарифе.

### Стоимость LLM

Стоимость не задана во frontend: API рассчитывает предварительную оценку при
загрузке и возвращает фактические затраты, накопленные во время обработки, по
`GET /api/v1/books/{book_id}/cost`. Прайс-лист задаётся JSON-переменной
`AI_READER_AI_MODEL_PRICE_LIST`; ключ — идентификатор модели, суммы — USD за
миллион токенов:

```bash
AI_READER_AI_MODEL_PRICE_LIST='{"gpt-5.6-luna":{"input_per_million_tokens":2.0,"cached_input_per_million_tokens":0.5,"output_per_million_tokens":8.0,"version":"2026-09"}}'
```

Если для модели нет записи, используются совместимые переменные
`AI_READER_AI_*_COST_PER_MILLION_TOKENS` и `AI_READER_AI_PRICING_VERSION`.

Для TTS укажите цену внешнего провайдера за час готового аудио через
`AI_READER_TTS_EXTERNAL_COST_PER_AUDIO_HOUR_USD`; по умолчанию она равна нулю.

PostgreSQL, Redis и MinIO доступны только внутри Docker-сети. Для диагностики
используйте `docker compose exec`; данные хранятся в named volumes.

## Локальный запуск без Docker

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d postgres redis minio
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

В отдельных терминалах при необходимости:

```bash
uv run celery -A app.workers.celery_app worker -Q processing --loglevel=INFO
uv run celery -A app.workers.celery_app worker -Q tts --loglevel=INFO
```

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
