from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional
from app.utils.validation_helpers import validate_start_time


class BookingBase(BaseModel):
    room_id: int
    start_time: datetime
    purpose: Optional[str] = None

    @validator("start_time")
    def check_start_time(cls, value):
        return validate_start_time(value)


class BookingCreate(BookingBase):
    required_capacity: int


class BookingUpdate(BaseModel):
    room_id: Optional[int] = None
    start_time: Optional[datetime] = None
    purpose: Optional[str] = None

    @validator("start_time")
    def check_start_time(cls, value):
        return validate_start_time(value)


class BookingResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    purpose: str

    class Config:
        orm_mode = True


class BookingOptimizeRequest(BaseModel):
    start_time: datetime
    purpose: str
    required_capacity: int

    class Config:
        orm_mode = True
