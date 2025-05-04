from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional

class BookingBase(BaseModel):
    room_id: int
    start_time: datetime
    purpose: Optional[str] = None

    @validator("start_time")
    def validate_start_time(cls, value):
        if value.minute != 0 or value.second != 0 or value.microsecond != 0:
            raise ValueError("Start time must be at the beginning of an hour (e.g., 13:00:00)")
        return value

class BookingCreate(BookingBase):
    required_capacity: int

class BookingUpdate(BaseModel):
    room_id: Optional[int] = None
    start_time: Optional[datetime] = None
    purpose: Optional[str] = None

    @validator("start_time")
    def validate_start_time(cls, value):
        if value and (value.minute != 0 or value.second != 0 or value.microsecond != 0):
            raise ValueError("Start time must be at the beginning of an hour (e.g., 13:00:00)")
        return value

class BookingResponse(BookingBase):
    id: int
    user_id: int
    end_time: datetime  # Included in response for clarity

    class Config:
        orm_mode = True

class BookingOptimizeRequest(BaseModel):
    start_time: datetime
    required_capacity: int

    @validator("start_time")
    def validate_start_time(cls, value):
        if value.minute != 0 or value.second != 0 or value.microsecond != 0:
            raise ValueError("Start time must be at the beginning of an hour (e.g., 13:00:00)")
        return value

class BookingOptimizeResponse(BaseModel):
    room_id: int
