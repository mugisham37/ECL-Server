from app.tasks.celery_app import celery_app


@celery_app.task(name="send_reset_password_email")
def send_reset_password_email(user_id: str, raw_token: str, ip_address: str) -> None:
    """Queue password reset email (SMTP integration)."""
    _ = (user_id, raw_token, ip_address)


@celery_app.task(name="send_invite_email")
def send_invite_email(invitation_id: str, raw_token: str) -> None:
    _ = (invitation_id, raw_token)


@celery_app.task(name="send_welcome_email")
def send_welcome_email(user_id: str, tenant_id: str) -> None:
    _ = (user_id, tenant_id)


@celery_app.task(name="send_verification_email")
def send_verification_email(user_id: str, raw_token: str) -> None:
    _ = (user_id, raw_token)


@celery_app.task(name="send_password_changed_email")
def send_password_changed_email(user_id: str, ip_address: str) -> None:
    _ = (user_id, ip_address)


@celery_app.task(name="send_welcome_to_tenant_email")
def send_welcome_to_tenant_email(user_id: str, tenant_id: str) -> None:
    _ = (user_id, tenant_id)
