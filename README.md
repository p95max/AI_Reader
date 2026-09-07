# AI Reader API

Backend-сервис AI Reader на FastAPI и Python 3.14.

## Быстрый старт

```bash
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

Сервис будет доступен на `http://127.0.0.1:8000`.
Интерактивная спецификация API: `http://127.0.0.1:8000/docs`.

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
  main.py       # точка входа FastAPI
tests/          # тесты
```

