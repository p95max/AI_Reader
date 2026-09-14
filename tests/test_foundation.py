from app.core.config import Settings
from app.workers.celery_app import celery_app


def test_default_infrastructure_urls() -> None:
    settings = Settings()

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url.startswith("redis://")
    assert settings.celery_broker_url.startswith("redis://")


def test_celery_uses_json_and_tracks_started_tasks() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.task_track_started is True


def test_settings_ignore_compose_only_dotenv_variables() -> None:
    settings = Settings(POSTGRES_DB="ai_reader", MINIO_ROOT_USER="minioadmin")

    assert settings.database_url.startswith("postgresql+psycopg://")
