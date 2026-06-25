from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_ulid
from app.modules.notifications.models import UserNotification
from app.modules.notifications.schemas import NotificationOut
from app.modules.settings.models import NotificationPreferences
from app.modules.tenants.models import TenantMembership
from app.core.enums import UserRole


def _to_out(row: UserNotification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        is_read=row.is_read,
        created_at=row.created_at,
    )


async def _pref_enabled(db: AsyncSession, user_id: str, pref_field: str) -> bool:
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return True
    return bool(getattr(row, pref_field, True))


async def create_notification_if_enabled(
    db: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    kind: str,
    pref_field: str,
    title: str,
    body: str,
) -> UserNotification | None:
    if not await _pref_enabled(db, user_id, pref_field):
        return None
    notif = UserNotification(
        id=new_ulid(),
        user_id=user_id,
        tenant_id=tenant_id,
        kind=kind,
        title=title,
        body=body,
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


async def notify_run_completed(
    db: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    run_name: str,
    run_id: str,
) -> None:
    await create_notification_if_enabled(
        db,
        user_id=user_id,
        tenant_id=tenant_id,
        kind="run_completed",
        pref_field="run_completed",
        title="Run completed",
        body=f'"{run_name}" finished successfully. View results for run {run_id[:8]}.',
    )


async def notify_run_failed(
    db: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    run_name: str,
    run_id: str,
) -> None:
    await create_notification_if_enabled(
        db,
        user_id=user_id,
        tenant_id=tenant_id,
        kind="run_failed",
        pref_field="run_failed",
        title="Run failed",
        body=f'"{run_name}" did not complete. Check the run detail for run {run_id[:8]}.',
    )


async def notify_member_joined_admins(
    db: AsyncSession,
    *,
    tenant_id: str,
    member_name: str,
    member_email: str,
) -> None:
    admin_roles = {UserRole.ADMINISTRATOR.value}
    result = await db.execute(
        select(TenantMembership.user_id).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
            TenantMembership.role.in_(admin_roles),
        )
    )
    for (admin_user_id,) in result.all():
        await create_notification_if_enabled(
            db,
            user_id=admin_user_id,
            tenant_id=tenant_id,
            kind="member_joined",
            pref_field="member_joined",
            title="New member joined",
            body=f"{member_name} ({member_email}) joined the workspace.",
        )


async def list_notifications(db: AsyncSession, user_id: str, limit: int = 20) -> list[NotificationOut]:
    result = await db.execute(
        select(UserNotification)
        .where(UserNotification.user_id == user_id)
        .order_by(UserNotification.created_at.desc())
        .limit(limit)
    )
    return [_to_out(row) for row in result.scalars().all()]


async def mark_read(db: AsyncSession, user_id: str, notification_id: str) -> None:
    await db.execute(
        update(UserNotification)
        .where(
            UserNotification.id == notification_id,
            UserNotification.user_id == user_id,
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )


async def mark_all_read(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(UserNotification)
        .where(UserNotification.user_id == user_id, UserNotification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
