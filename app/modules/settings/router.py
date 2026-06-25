from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DbSession
from app.modules.settings.schemas import (
    NotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)
from app.modules.settings import service
from app.modules.notifications.schemas import NotificationsListResponse
from app.modules.notifications import service as notifications_service
from app.modules.auth.schemas import MessageResponse

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


@router.get("/notifications")
async def list_notifications_endpoint(
    current_user: CurrentUser,
    db: DbSession,
) -> NotificationsListResponse:
    data = await notifications_service.list_notifications(db, current_user.id)
    return NotificationsListResponse(data=data)


@router.patch("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read_endpoint(
    notification_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    await notifications_service.mark_read(db, current_user.id, notification_id)


@router.post("/notifications/read-all")
async def mark_all_notifications_read_endpoint(
    current_user: CurrentUser,
    db: DbSession,
) -> MessageResponse:
    await notifications_service.mark_all_read(db, current_user.id)
    return MessageResponse(message="All notifications marked as read.")
