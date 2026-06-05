from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_ulid
from app.modules.settings.models import NotificationPreferences
from app.modules.settings.schemas import (
    DEFAULT_NOTIFICATION_PREFERENCES,
    NotificationPreferencesOut,
    UpdateNotificationPreferencesRequest,
)


def _to_out(row: NotificationPreferences) -> NotificationPreferencesOut:
    return NotificationPreferencesOut(
        id=row.id,
        run_completed=row.run_completed,
        run_failed=row.run_failed,
        weekly_summary=row.weekly_summary,
        member_joined=row.member_joined,
        product_updates=row.product_updates,
    )


async def get_notification_prefs(
    db: AsyncSession, user_id: str
) -> NotificationPreferencesOut:
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return DEFAULT_NOTIFICATION_PREFERENCES
    return _to_out(row)


async def upsert_notification_prefs(
    db: AsyncSession,
    user_id: str,
    req: UpdateNotificationPreferencesRequest,
) -> NotificationPreferencesOut:
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if not row:
        row = NotificationPreferences(
            id=new_ulid(),
            user_id=user_id,
            run_completed=DEFAULT_NOTIFICATION_PREFERENCES.run_completed,
            run_failed=DEFAULT_NOTIFICATION_PREFERENCES.run_failed,
            weekly_summary=DEFAULT_NOTIFICATION_PREFERENCES.weekly_summary,
            member_joined=DEFAULT_NOTIFICATION_PREFERENCES.member_joined,
            product_updates=DEFAULT_NOTIFICATION_PREFERENCES.product_updates,
        )
        db.add(row)

    if req.run_completed is not None:
        row.run_completed = req.run_completed
    if req.run_failed is not None:
        row.run_failed = req.run_failed
    if req.weekly_summary is not None:
        row.weekly_summary = req.weekly_summary
    if req.member_joined is not None:
        row.member_joined = req.member_joined
    if req.product_updates is not None:
        row.product_updates = req.product_updates

    await db.flush()
    return _to_out(row)
