from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_reader",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Do not acknowledge long-running work before it completes.  If a worker
    # disappears, Redis can redeliver its message and the task's durable
    # checkpoints decide what still needs to be done.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "ai_reader.books.*": {"queue": "processing"},
        "ai_reader.processing.*": {"queue": "processing"},
        "ai_reader.tts.*": {"queue": "tts"},
    },
)
