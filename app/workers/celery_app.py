from time import perf_counter

import structlog
from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.debug)
logger = structlog.get_logger(__name__)
_task_started_at: dict[str, float] = {}

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


@task_prerun.connect
def log_worker_task_started(task_id: str | None = None, task=None, **_kwargs: object) -> None:
    if task_id is None or task is None:
        return
    _task_started_at[task_id] = perf_counter()
    logger.info("worker_task_started", task_id=task_id, task_name=task.name)


@task_postrun.connect
def log_worker_task_finished(
    task_id: str | None = None,
    task=None,
    state: str | None = None,
    **_kwargs: object,
) -> None:
    if task_id is None or task is None:
        return
    started_at = _task_started_at.pop(task_id, None)
    logger.info(
        "worker_task_finished",
        task_id=task_id,
        task_name=task.name,
        state=state,
        duration_ms=round((perf_counter() - started_at) * 1_000) if started_at else None,
    )


@task_failure.connect
def log_worker_task_failure(
    task_id: str | None = None,
    exception: Exception | None = None,
    sender=None,
    **_kwargs: object,
) -> None:
    logger.error(
        "worker_task_failed",
        task_id=task_id,
        task_name=getattr(sender, "name", None),
        error_type=type(exception).__name__ if exception else None,
        error=str(exception) if exception else None,
    )
