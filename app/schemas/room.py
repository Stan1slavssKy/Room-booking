from pydantic import BaseModel
from typing import Optional

class RoomBase(BaseModel):
    name: str
    capacity: int
    location: Optional[str] = None

class RoomCreate(RoomBase):
    pass

class RoomUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    location: Optional[str] = None

class RoomResponse(RoomBase):
    id: int

    class Config:
        orm_mode = True
