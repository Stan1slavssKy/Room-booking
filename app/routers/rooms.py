from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db import SessionLocal
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/rooms",
    tags=["rooms"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(room: RoomCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Create a new meeting room.
    Requires authentication.
    """
    db_room = Room(**room.dict())
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room


@router.get("/", response_model=List[RoomResponse])
def get_rooms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of all meeting rooms.
    """
    rooms = db.query(Room).offset(skip).limit(limit).all()
    return rooms


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific meeting room by ID.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(room_id: int, room_update: RoomUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Update a meeting room's details.
    Requires authentication.
    """
    db_room = db.query(Room).filter(Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    
    update_data = room_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_room, key, value)
    
    db.commit()
    db.refresh(db_room)
    return db_room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Delete a meeting room.
    Requires authentication.
    """
    db_room = db.query(Room).filter(Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    
    db.delete(db_room)
    db.commit()
    return None
