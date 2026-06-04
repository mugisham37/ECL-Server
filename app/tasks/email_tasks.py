import asyncio

from app.tasks.celery_app import celery_app


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


@celery_app.task(
    name="send_verification_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_verification_email(self, user_id: str, raw_token: str) -> None:  # type: ignore[misc]
    async def _send() -> None:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.database import AsyncSessionLocal
        from app.modules.auth.models import User

        s = get_settings()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return
        await send_email(
            to=user.email,
            subject="Verify your ECL Platform email address",
            template_name="verify_email.html",
            context={
                "user_name": user.name,
                "verify_url": f"{s.frontend_url}/verify-email?token={raw_token}",
            },
        )

    _run(_send())


@celery_app.task(
    name="send_reset_password_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_reset_password_email(self, user_id: str, raw_token: str, ip_address: str) -> None:  # type: ignore[misc]
    async def _send() -> None:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.database import AsyncSessionLocal
        from app.modules.auth.models import User

        s = get_settings()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return
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

    _run(_send())


@celery_app.task(
    name="send_invite_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_invite_email(self, invitation_id: str, raw_token: str) -> None:  # type: ignore[misc]
    async def _send() -> None:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.database import AsyncSessionLocal
        from app.modules.invites.models import Invitation
        from app.modules.tenants.models import Tenant
        from app.modules.auth.models import User

        s = get_settings()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Invitation, Tenant, User)
                .join(Tenant, Tenant.id == Invitation.tenant_id)
                .join(User, User.id == Invitation.invited_by_user_id)
                .where(Invitation.id == invitation_id)
            )
            row = result.first()
            if not row:
                return
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

    _run(_send())


@celery_app.task(
    name="send_welcome_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_welcome_email(self, user_id: str, tenant_id: str) -> None:  # type: ignore[misc]
    async def _send() -> None:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.database import AsyncSessionLocal
        from app.modules.auth.models import User
        from app.modules.tenants.models import Tenant

        s = get_settings()
        async with AsyncSessionLocal() as db:
            user_r = await db.execute(select(User).where(User.id == user_id))
            tenant_r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            user = user_r.scalar_one_or_none()
            tenant = tenant_r.scalar_one_or_none()
            if not user or not tenant:
                return
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

    _run(_send())


@celery_app.task(
    name="send_welcome_to_tenant_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_welcome_to_tenant_email(self, user_id: str, tenant_id: str) -> None:  # type: ignore[misc]
    send_welcome_email.apply_async(args=[user_id, tenant_id])


@celery_app.task(
    name="send_password_changed_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5},
    default_retry_delay=60,
)
def send_password_changed_email(self, user_id: str, ip_address: str) -> None:  # type: ignore[misc]
    async def _send() -> None:
        from sqlalchemy import select

        from app.config import get_settings
        from app.core.email import send_email
        from app.database import AsyncSessionLocal
        from app.modules.auth.models import User

        s = get_settings()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return
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

    _run(_send())
