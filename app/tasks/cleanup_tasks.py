from app.tasks.celery_app import celery_app


@celery_app.task(name="expire_password_reset_tokens")
def expire_password_reset_tokens() -> None:
    pass


@celery_app.task(name="expire_invitations")
def expire_invitations() -> None:
    pass


@celery_app.task(name="purge_revoked_refresh_tokens")
def purge_revoked_refresh_tokens() -> None:
    pass


@celery_app.task(name="purge_old_sessions")
def purge_old_sessions() -> None:
    pass
