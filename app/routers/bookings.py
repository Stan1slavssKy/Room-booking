from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session

from app.db import get_db
from app.models.booking import Booking
from app.models.room import Room
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
)
from app.utils.auth import get_current_user
from app.utils.scheduler import find_optimal_room

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new one-hour booking for a room.
    Requires authentication.
    """
    # Check if room exists
    room = db.query(Room).filter(Room.id == booking.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    # Calculate end_time (1 hour after start_time)
    end_time = booking.start_time + timedelta(hours=1)

    # Check for overlapping bookings
    overlapping = (
        db.query(Booking)
        .filter(
            Booking.room_id == booking.room_id,
            Booking.start_time < end_time,
            Booking.start_time >= booking.start_time - timedelta(hours=1),
        )
        .first()
    )
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room is already booked for this time slot",
        )

    db_booking = Booking(
        room_id=booking.room_id,
        user_id=current_user["id"],
        start_time=booking.start_time,
        purpose=booking.purpose,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    # Add end_time to response
    db_booking.end_time = end_time
    return db_booking


@router.get("/", response_model=List[BookingResponse])
def get_bookings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of all bookings.
    """
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    # Add end_time to each booking for response
    for booking in bookings:
        booking.end_time = booking.start_time + timedelta(hours=1)
    return bookings


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific booking by ID.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )
    # Add end_time to response
    booking.end_time = booking.start_time + timedelta(hours=1)
    return booking


@router.put("/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    booking_update: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a booking's details (one-hour duration).
    Requires authentication and ownership.
    """
    db_booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )

    if db_booking.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this booking",
        )

    # Calculate new start_time and end_time if updated
    new_start_time = booking_update.start_time or db_booking.start_time
    new_end_time = new_start_time + timedelta(hours=1)

    # Check for overlapping bookings if room or time is updated
    if booking_update.room_id or booking_update.start_time:
        room_id = booking_update.room_id or db_booking.room_id
        overlapping = (
            db.query(Booking)
            .filter(
                Booking.room_id == room_id,
                Booking.id != booking_id,
                Booking.start_time < new_end_time,
                Booking.start_time >= new_start_time - timedelta(hours=1),
            )
            .first()
        )
        if overlapping:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room is already booked for this time slot",
            )

    update_data = booking_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_booking, key, value)

    db.commit()
    db.refresh(db_booking)
    # Add end_time to response
    db_booking.end_time = db_booking.start_time + timedelta(hours=1)
    return db_booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a booking.
    Requires authentication and ownership.
    """
    db_booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )

    if db_booking.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this booking",
        )

    db.delete(db_booking)
    db.commit()
    return None


@router.post(
    "/optimize", response_model=BookingResponse, status_code=status.HTTP_201_CREATED
)
def optimize_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Find and book the optimal room for a one-hour slot.
    Requires authentication.
    """
    end_time = booking.start_time + timedelta(hours=1)
    optimal_room = find_optimal_room(
        db, booking.start_time, end_time, booking.required_capacity
    )
    if not optimal_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No suitable room available"
        )

    db_booking = Booking(
        room_id=optimal_room.id,
        user_id=current_user["id"],
        start_time=booking.start_time,
        purpose=booking.purpose,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    # Add end_time to response
    db_booking.end_time = db_booking.start_time + timedelta(hours=1)
    return db_booking


@router.get("/available-slots", response_model=List[datetime])
def get_available_slots(
    room_id: int, booking_date: date, db: Session = Depends(get_db)
):
    """
    Retrieve available one-hour time slots for a room on a specific date.
    """
    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    # Define possible slots (e.g., 09:00 to 17:00)
    start_hour = 9
    end_hour = 17
    available_slots = []
    booking_date = datetime.combine(booking_date, datetime.min.time())

    # Check each hour for availability
    for hour in range(start_hour, end_hour):
        slot_start = booking_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        slot_end = slot_start + timedelta(hours=1)

        # Check for overlapping bookings
        overlapping = (
            db.query(Booking)
            .filter(
                Booking.room_id == room_id,
                Booking.start_time < slot_end,
                Booking.start_time >= slot_start - timedelta(hours=1),
            )
            .first()
        )

        if not overlapping:
            available_slots.append(slot_start)

    return available_slots
