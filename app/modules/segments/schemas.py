from datetime import datetime

from pydantic import BaseModel, Field


class CreateSegmentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str | None = Field(default=None, max_length=50)


class UpdateSegmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class SegmentOut(BaseModel):
    id: str
    name: str
    code: str | None
    is_active: bool
    runs_count: int
    created_at: datetime


class SegmentListResponse(BaseModel):
    data: list[SegmentOut]


class SegmentResponse(BaseModel):
    data: SegmentOut


class BatchCreateSegmentsRequest(BaseModel):
    segments: list[CreateSegmentRequest] = Field(min_length=1, max_length=50)
