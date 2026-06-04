from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreateCollateralTypeRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    haircut: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), decimal_places=2)
    time_to_realize: int = Field(ge=0)


class UpdateCollateralTypeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    haircut: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"), decimal_places=2)
    time_to_realize: int | None = Field(default=None, ge=0)


class CollateralTypeOut(BaseModel):
    id: str
    name: str
    haircut: Decimal
    time_to_realize: int
    created_at: datetime


class CollateralTypeListResponse(BaseModel):
    data: list[CollateralTypeOut]


class CollateralTypeResponse(BaseModel):
    data: CollateralTypeOut


class BatchCreateCollateralTypesRequest(BaseModel):
    items: list[CreateCollateralTypeRequest] = Field(min_length=1, max_length=50)
