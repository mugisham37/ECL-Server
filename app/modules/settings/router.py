from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.modules.settings.schemas import (
    NotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)
from app.modules.settings import service

router = APIRouter(prefix="/me", tags=["settings"])


@router.get("/notification-preferences")
async def get_notification_preferences(
    current_user: CurrentUser,
    db: DbSession,
) -> NotificationPreferencesResponse:
    data = await service.get_notification_prefs(db, current_user.id)
    return NotificationPreferencesResponse(data=data)


@router.patch("/notification-preferences")
async def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> NotificationPreferencesResponse:
    data = await service.upsert_notification_prefs(db, current_user.id, body)
    return NotificationPreferencesResponse(data=data)
