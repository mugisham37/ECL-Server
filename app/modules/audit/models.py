from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditEvent(StrEnum):
    USER_REGISTER = "user.register"
    EMAIL_VERIFIED = "user.email_verified"
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGIN_LOCKED = "auth.login.locked"
    LOGOUT = "auth.logout"
    LOGOUT_ALL = "auth.logout_all"
    PASSWORD_RESET_REQ = "auth.password_reset.requested"
    PASSWORD_RESET_DONE = "auth.password_reset.completed"
    PASSWORD_CHANGED = "auth.password.changed"
    TOKEN_REFRESHED = "auth.token.refreshed"
    TENANT_SWITCHED = "auth.tenant.switched"
    INVITE_SENT = "invite.sent"
    INVITE_BATCH_SENT = "invite.batch_sent"
    INVITE_ACCEPTED = "invite.accepted"
    SESSION_REVOKED = "session.revoked"
    SESSIONS_ALL_REVOKED = "session.all_revoked"
    TOTP_ENROLLED = "mfa.totp.enrolled"
    TOTP_DISABLED = "mfa.totp.disabled"
    TOTP_VERIFIED = "mfa.totp.verified"
    TOTP_FAILED = "mfa.totp.failed"
    RECOVERY_CODE_USED = "mfa.recovery_code.used"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("audit_user_event_time_idx", "user_id", "event_type", "created_at"),
        Index("audit_created_at_idx", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="success")
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
