from pydantic import BaseModel


class NotificationPreferencesOut(BaseModel):
    id: str | None = None
    run_completed: bool
    run_failed: bool
    weekly_summary: bool
    member_joined: bool
    product_updates: bool


class UpdateNotificationPreferencesRequest(BaseModel):
    run_completed: bool | None = None
    run_failed: bool | None = None
    weekly_summary: bool | None = None
    member_joined: bool | None = None
    product_updates: bool | None = None


class NotificationPreferencesResponse(BaseModel):
    data: NotificationPreferencesOut


DEFAULT_NOTIFICATION_PREFERENCES = NotificationPreferencesOut(
    id=None,
    run_completed=True,
    run_failed=True,
    weekly_summary=False,
    member_joined=True,
    product_updates=False,
)
