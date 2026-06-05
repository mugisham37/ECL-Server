from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Inbound ───────────────────────────────────────────────────────────────────

class OnboardingProfileIn(BaseModel):
    institution_name: str = Field(min_length=2, max_length=200)
    currency: str = Field(min_length=1, max_length=8)
    timezone: str = Field(min_length=1, max_length=64)
    cadence: str

    @field_validator("cadence")
    @classmethod
    def validate_cadence(cls, v: str) -> str:
        normalised = v.lower()
        if normalised not in {"monthly", "quarterly"}:
            raise ValueError("cadence must be Monthly or Quarterly")
        return normalised

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.strip().upper()


class OnboardingSegmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)


class OnboardingCollateralIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    haircut: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    ttr: int = Field(ge=0)


class OnboardingInviteIn(BaseModel):
    email: EmailStr
    role: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class CompleteOnboardingRequest(BaseModel):
    profile: OnboardingProfileIn
    segments: list[OnboardingSegmentIn] = Field(min_length=1, max_length=50)
    collateral: list[OnboardingCollateralIn] = Field(min_length=1, max_length=50)
    invites: list[OnboardingInviteIn] = Field(default_factory=list, max_length=20)


class SaveProgressRequest(BaseModel):
    progress: dict[str, Any]


# ── Outbound ──────────────────────────────────────────────────────────────────

class OnboardingSegmentOut(BaseModel):
    id: str
    name: str
    code: str | None


class OnboardingCollateralOut(BaseModel):
    id: str
    name: str
    haircut: Decimal
    time_to_realize: int


class OnboardingStatusData(BaseModel):
    is_complete: bool
    completed_at: datetime | None
    progress: dict[str, Any] | None
    segments: list[OnboardingSegmentOut]
    collateral_types: list[OnboardingCollateralOut]


class OnboardingStatusResponse(BaseModel):
    data: OnboardingStatusData


class OnboardingCompleteResponse(BaseModel):
    data: dict[str, str]
    message: str


class SaveProgressResponse(BaseModel):
    data: dict[str, str]
    message: str
