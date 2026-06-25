from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    is_read: bool
    created_at: datetime


class NotificationsListResponse(BaseModel):
    data: list[NotificationOut]
