from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ecl_tasks",
    broker=settings.redis_celery_url,
    backend=settings.redis_celery_url,
    include=["app.tasks.email_tasks", "app.tasks.cleanup_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_soft_time_limit=30,
    task_time_limit=60,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
