import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from typing import Any

from app.core.email_task_utils import handle_email_task_exception
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

_log = get_logger("email")


def _run(coro) -> Any:  # type: ignore[no-untyped-def]
    """Run an async coroutine from a sync Celery task and return its result.

    asyncio.run() raises RuntimeError when called from inside an already-running
    event loop (eager/inline mode under FastAPI). In that case, spin a dedicated
    thread with its own fresh event loop instead.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


@asynccontextmanager  # type: ignore[misc]
async def _task_session():  # type: ignore[no-untyped-def]
    """Fresh NullPool database session for each Celery task execution.

    Celery workers call asyncio.run() per task, which creates then destroys an
    event loop. The shared AsyncSessionLocal engine caches asyncpg connections
    bound to their creation loop. On a retry a brand-new loop sees those stale
    connections and raises 'Future attached to a different loop'. NullPool
    disables connection caching so every task run gets a clean connection.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings

    s = get_settings()
    engine = create_async_engine(s.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            yield session
    finally:
        await engine.dispose()


def _retry_not_committed(task, entity_label: str, entity_id: str) -> None:
    retries = task.request.retries
    _log.warning(
        "email_entity_not_found",
        task=task.name,
        entity=entity_label,
        entity_id=entity_id,
        retries=retries,
    )
    if retries >= task.max_retries:
        _log.error(
            "email_send_gave_up",
            task=task.name,
            entity=entity_label,
            entity_id=entity_id,
            reason="entity_not_committed",
        )
        return
    raise task.retry(
        countdown=2,
        max_retries=3,
        exc=RuntimeError(f"{entity_label} {entity_id} not committed yet — will retry"),
    )


@celery_app.task(name="send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, user_id: str, raw_token: str) -> None:  # type: ignore[misc]
    _log.info("email_task_started", task="send_verification_email", user_id=user_id)

    async def _send() -> tuple[bool, str | None]:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.modules.auth.models import User

        s = get_settings()
        async with _task_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

        if not user:
            return False, None

        await send_email(
            to=user.email,
            subject="Verify your ECL Platform email address",
            template_name="verify_email.html",
            context={
                "user_name": user.name,
                "verify_url": f"{s.frontend_url}/verify-email?token={raw_token}",
            },
        )
        return True, user.email

    try:
        found, recipient = _run(_send())
    except Exception as exc:
        handle_email_task_exception(
            self, exc, task_name="send_verification_email", user_id=user_id
        )
        return

    if not found:
        _retry_not_committed(self, "user", user_id)
        return

    _log.info(
        "email_task_completed",
        task="send_verification_email",
        user_id=user_id,
        recipient=recipient,
    )


@celery_app.task(name="send_reset_password_email", bind=True, max_retries=3)
def send_reset_password_email(self, user_id: str, raw_token: str, ip_address: str) -> None:  # type: ignore[misc]
    _log.info("email_task_started", task="send_reset_password_email", user_id=user_id)

    async def _send() -> tuple[bool, str | None]:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.modules.auth.models import User

        s = get_settings()
        async with _task_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

        if not user:
            return False, None

        await send_email(
            to=user.email,
            subject="Reset your ECL Platform password",
            template_name="reset_password.html",
            context={
                "user_name": user.name,
                "reset_url": f"{s.frontend_url}/reset-password?token={raw_token}",
                "ip_address": ip_address,
            },
        )
        return True, user.email

    try:
        found, recipient = _run(_send())
    except Exception as exc:
        handle_email_task_exception(
            self, exc, task_name="send_reset_password_email", user_id=user_id
        )
        return

    if not found:
        _retry_not_committed(self, "user", user_id)
        return

    _log.info(
        "email_task_completed",
        task="send_reset_password_email",
        user_id=user_id,
        recipient=recipient,
    )


@celery_app.task(name="send_invite_email", bind=True, max_retries=3)
def send_invite_email(self, invitation_id: str, raw_token: str) -> None:  # type: ignore[misc]
    _log.info("email_task_started", task="send_invite_email", invitation_id=invitation_id)

    async def _send() -> tuple[bool, str | None]:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.modules.auth.models import User
        from app.modules.invites.models import Invitation
        from app.modules.tenants.models import Tenant

        s = get_settings()
        async with _task_session() as db:
            result = await db.execute(
                select(Invitation, Tenant, User)
                .join(Tenant, Tenant.id == Invitation.tenant_id)
                .join(User, User.id == Invitation.invited_by_user_id)
                .where(Invitation.id == invitation_id)
            )
            row = result.first()

        if not row:
            return False, None

        inv, tenant, inviter = row
        await send_email(
            to=inv.email,
            subject=f"You've been invited to join {tenant.name} on ECL Platform",
            template_name="invite.html",
            context={
                "inviter_name": inviter.name,
                "tenant_name": tenant.name,
                "role": inv.role.capitalize(),
                "accept_url": f"{s.frontend_url}/invite?token={raw_token}",
            },
        )
        return True, inv.email

    try:
        found, recipient = _run(_send())
    except Exception as exc:
        handle_email_task_exception(
            self, exc, task_name="send_invite_email", invitation_id=invitation_id
        )
        return

    if not found:
        _retry_not_committed(self, "invitation", invitation_id)
        return

    _log.info(
        "email_task_completed",
        task="send_invite_email",
        invitation_id=invitation_id,
        recipient=recipient,
    )


@celery_app.task(name="send_welcome_email", bind=True, max_retries=3)
def send_welcome_email(self, user_id: str, tenant_id: str) -> None:  # type: ignore[misc]
    _log.info(
        "email_task_started",
        task="send_welcome_email",
        user_id=user_id,
        tenant_id=tenant_id,
    )

    async def _send() -> tuple[bool, str | None]:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.modules.auth.models import User
        from app.modules.tenants.models import Tenant

        s = get_settings()
        async with _task_session() as db:
            user_r = await db.execute(select(User).where(User.id == user_id))
            tenant_r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            user = user_r.scalar_one_or_none()
            tenant = tenant_r.scalar_one_or_none()

        if not user or not tenant:
            return False, None

        await send_email(
            to=user.email,
            subject="Welcome to ECL Platform",
            template_name="welcome.html",
            context={
                "user_name": user.name,
                "tenant_name": tenant.name,
                "dashboard_url": f"{s.frontend_url}/dashboard",
            },
        )
        return True, user.email

    try:
        found, recipient = _run(_send())
    except Exception as exc:
        handle_email_task_exception(
            self,
            exc,
            task_name="send_welcome_email",
            user_id=user_id,
            tenant_id=tenant_id,
        )
        return

    if not found:
        _retry_not_committed(self, "user_or_tenant", f"{user_id}/{tenant_id}")
        return

    _log.info(
        "email_task_completed",
        task="send_welcome_email",
        user_id=user_id,
        tenant_id=tenant_id,
        recipient=recipient,
    )


@celery_app.task(name="send_welcome_to_tenant_email", bind=True)
def send_welcome_to_tenant_email(self, user_id: str, tenant_id: str) -> None:  # type: ignore[misc]
    try:
        send_welcome_email.apply_async(args=[user_id, tenant_id])
        _log.info(
            "email_task_dispatched",
            task="send_welcome_email",
            user_id=user_id,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        _log.warning(
            "email_task_dispatch_failed",
            task="send_welcome_to_tenant_email",
            user_id=user_id,
            exc=str(exc),
            exc_info=True,
        )


@celery_app.task(name="send_password_changed_email", bind=True, max_retries=3)
def send_password_changed_email(self, user_id: str, ip_address: str) -> None:  # type: ignore[misc]
    _log.info("email_task_started", task="send_password_changed_email", user_id=user_id)

    async def _send() -> tuple[bool, str | None]:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.modules.auth.models import User

        s = get_settings()
        async with _task_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

        if not user:
            return False, None

        await send_email(
            to=user.email,
            subject="Your ECL Platform password was changed",
            template_name="password_changed.html",
            context={
                "user_name": user.name,
                "ip_address": ip_address,
                "sessions_url": f"{s.frontend_url}/account/security",
            },
        )
        return True, user.email

    try:
        found, recipient = _run(_send())
    except Exception as exc:
        handle_email_task_exception(
            self, exc, task_name="send_password_changed_email", user_id=user_id
        )
        return

    if not found:
        _retry_not_committed(self, "user", user_id)
        return

    _log.info(
        "email_task_completed",
        task="send_password_changed_email",
        user_id=user_id,
        recipient=recipient,
    )
