from enum import StrEnum


class UserRole(StrEnum):
    ADMINISTRATOR = "administrator"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class MemberStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TenantPlan(StrEnum):
    TRIAL = "trial"
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class TenantStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class DeviceType(StrEnum):
    LAPTOP = "laptop"
    PHONE = "phone"
    UNKNOWN = "unknown"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReportingCadence(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
