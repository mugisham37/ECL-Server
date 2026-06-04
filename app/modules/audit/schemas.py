from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    event_type: str
    status: str
    error_code: str | None
    details: dict | None  # type: ignore[type-arg]
    created_at: datetime


class AuditLogsResponse(BaseModel):
    data: list[AuditLogOut]
