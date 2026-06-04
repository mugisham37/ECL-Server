import asyncio

from app.tasks.celery_app import celery_app


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


@celery_app.task(name="expire_invitations")
def expire_invitations() -> int:
    async def _run_async() -> int:
        from datetime import UTC, datetime

        from sqlalchemy import update

        from app.core.enums import InvitationStatus
        from app.database import AsyncSessionLocal
        from app.modules.invites.models import Invitation

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(Invitation)
                .where(
                    Invitation.status == InvitationStatus.PENDING.value,
                    Invitation.expires_at < datetime.now(UTC),
                )
                .values(status=InvitationStatus.EXPIRED.value)
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    return _run(_run_async())


@celery_app.task(name="expire_password_reset_tokens")
def expire_password_reset_tokens() -> int:
    async def _run_async() -> int:
        from datetime import UTC, datetime

        from sqlalchemy import delete

        from app.database import AsyncSessionLocal
        from app.modules.auth.models import PasswordResetToken

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(PasswordResetToken).where(
                    PasswordResetToken.expires_at < datetime.now(UTC),
                    PasswordResetToken.used_at.is_(None),
                )
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    return _run(_run_async())


@celery_app.task(name="purge_revoked_refresh_tokens")
def purge_revoked_refresh_tokens() -> int:
    async def _run_async() -> int:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import delete

        from app.database import AsyncSessionLocal
        from app.modules.sessions.models import RefreshToken

        cutoff = datetime.now(UTC) - timedelta(days=30)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(RefreshToken).where(
                    RefreshToken.is_revoked.is_(True),
                    RefreshToken.expires_at < cutoff,
                )
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    return _run(_run_async())


@celery_app.task(name="purge_old_sessions")
def purge_old_sessions() -> int:
    async def _run_async() -> int:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import delete

        from app.database import AsyncSessionLocal
        from app.modules.sessions.models import Session

        cutoff = datetime.now(UTC) - timedelta(days=90)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(Session).where(Session.last_active_at < cutoff)
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    return _run(_run_async())


@celery_app.task(name="purge_expired_token_blacklist")
def purge_expired_token_blacklist() -> int:
    async def _run_async() -> int:
        from datetime import UTC, datetime

        from sqlalchemy import delete

        from app.database import AsyncSessionLocal
        from app.modules.auth.models import TokenBlacklist

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(TokenBlacklist).where(
                    TokenBlacklist.expires_at < datetime.now(UTC)
                )
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    return _run(_run_async())
