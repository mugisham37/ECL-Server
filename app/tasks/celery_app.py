from celery import Celery
from celery.schedules import crontab

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
    beat_schedule={
        "expire-invitations": {
            "task": "expire_invitations",
            "schedule": crontab(hour=0, minute=0),
        },
        "expire-password-reset-tokens": {
            "task": "expire_password_reset_tokens",
            "schedule": crontab(hour=0, minute=30),
        },
        "purge-revoked-refresh-tokens": {
            "task": "purge_revoked_refresh_tokens",
            "schedule": crontab(hour=1, minute=0),
        },
        "purge-old-sessions": {
            "task": "purge_old_sessions",
            "schedule": crontab(hour=2, minute=0),
        },
        "purge-expired-token-blacklist": {
            "task": "purge_expired_token_blacklist",
            "schedule": crontab(minute="*/30"),
        },
    },
)
