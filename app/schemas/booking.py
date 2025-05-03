from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BookingBase(BaseModel):
    room_id: int
    start_time: datetime
    purpose: Optional[str] = None

class BookingCreate(BookingBase):
    required_capacity: int

class BookingUpdate(BaseModel):
    room_id: Optional[int] = None
    start_time: Optional[datetime] = None
    purpose: Optional[str] = None

class BookingResponse(BookingBase):
    id: int
    user_id: int
    end_time: datetime  # Included in response for clarity

    class Config:
        orm_mode = True