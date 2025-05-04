from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.booking import Booking
from app.models.room import Room
from app.schemas.booking import BookingCreate, BookingUpdate, BookingResponse, BookingOptimizeRequest
from app.utils.auth import get_current_user
from app.utils.scheduler import find_optimal_room
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)

@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
    description="Create a new one-hour booking for a room at the start of an hour. Requires authentication."
)
def create_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new one-hour booking for a room at the start of an hour.
    Requires authentication.

    - **room_id**: ID of the room to book.
    - **start_time**: Start time of the booking (must be at the start of an hour).
    - **purpose**: Purpose of the booking.
    - **required_capacity**: Required room capacity.

    Returns the created booking with ID, room ID, user ID, start time, end time, and purpose.
    """
    logger.debug(f"Creating booking for user: {current_user['username']}, room_id: {booking.room_id}")

    # Check if room exists and capacity is sufficient
    room = db.query(Room).filter(Room.id == booking.room_id).first()
    if not room:
        logger.error(f"Room not found: {booking.room_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.capacity < booking.required_capacity:
        logger.error(f"Room capacity insufficient: {room.capacity} < {booking.required_capacity}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room capacity insufficient")

    # Validate start_time is at the start of an hour
    if booking.start_time.minute != 0 or booking.start_time.second != 0:
        logger.error(f"Invalid start_time: {booking.start_time}, must be at start of hour")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be at the start of an hour")

    # Calculate end_time
    end_time = booking.start_time + timedelta(hours=1)
    logger.debug(f"Calculated end_time: {end_time}")

    # Check for overlapping bookings
    overlapping = db.query(Booking).filter(
        Booking.room_id == booking.room_id,
        Booking.start_time < end_time,
        Booking.end_time > booking.start_time
    ).first()
    if overlapping:
        logger.error(f"Overlapping booking found for room_id: {booking.room_id}, time: {booking.start_time} to {end_time}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is already booked for this time slot")

    # Create booking
    db_booking = Booking(
        room_id=booking.room_id,
        user_id=current_user["id"],
        start_time=booking.start_time,
        end_time=end_time,
        purpose=booking.purpose,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    logger.debug(f"Created booking: {db_booking.id}, end_time: {db_booking.end_time}")
    return db_booking

@router.get(
    "/",
    response_model=List[BookingResponse],
    summary="List all bookings",
    description="Retrieve a paginated list of bookings."
)
def get_bookings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieve a list of all bookings.

    - **skip**: Number of bookings to skip.
    - **limit**: Maximum number of bookings to return.

    Returns a list of bookings with ID, room ID, user ID, start time, end time, and purpose.
    """
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    logger.debug(f"Retrieved {len(bookings)} bookings")
    return bookings

@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get a booking by ID",
    description="Retrieve a specific booking by its ID."
)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific booking by ID.

    - **booking_id**: ID of the booking to retrieve.

    Returns the booking details.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        logger.error(f"Booking not found: {booking_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    logger.debug(f"Retrieved booking: {booking_id}")
    return booking

@router.put(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Update a booking",
    description="Update a booking's details (one-hour duration). Requires authentication and ownership."
)
def update_booking(
    booking_id: int,
    booking_update: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a booking's details (one-hour duration).
    Requires authentication and ownership.

    - **booking_id**: ID of the booking to update.
    - **room_id**: (Optional) New room ID.
    - **start_time**: (Optional) New start time.
    - **purpose**: (Optional) New purpose.

    Returns the updated booking.
    """
    db_booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not db_booking:
        logger.error(f"Booking not found: {booking_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if db_booking.user_id != current_user["id"]:
        logger.error(f"User {current_user['username']} not authorized to update booking {booking_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this booking")

    # Calculate new start_time and end_time
    new_start_time = booking_update.start_time or db_booking.start_time
    new_end_time = new_start_time + timedelta(hours=1)

    # Validate new start_time
    if new_start_time.minute != 0 or new_start_time.second != 0:
        logger.error(f"Invalid start_time: {new_start_time}, must be at start of hour")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be at the start of an hour")

    # Check for overlapping bookings if room or time is updated
    if booking_update.room_id or booking_update.start_time:
        room_id = booking_update.room_id or db_booking.room_id
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            logger.error(f"Room not found: {room_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        overlapping = db.query(Booking).filter(
            Booking.room_id == room_id,
            Booking.id != booking_id,
            Booking.start_time < new_end_time,
            Booking.end_time > new_start_time
        ).first()
        if overlapping:
            logger.error(f"Overlapping booking found for room_id: {room_id}, time: {new_start_time} to {new_end_time}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is already booked for this time slot")

    # Update booking
    update_data = booking_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_booking, key, value)
    db_booking.start_time = new_start_time
    db_booking.end_time = new_end_time
    db.commit()
    db.refresh(db_booking)
    logger.debug(f"Updated booking: {booking_id}, end_time: {db_booking.end_time}")
    return db_booking

@router.delete(
    "/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a booking",
    description="Delete a booking. Requires authentication and ownership."
)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a booking.
    Requires authentication and ownership.

    - **booking_id**: ID of the booking to delete.
    """
    db_booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not db_booking:
        logger.error(f"Booking not found: {booking_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if db_booking.user_id != current_user["id"]:
        logger.error(f"User {current_user['username']} not authorized to delete booking {booking_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this booking")

    db.delete(db_booking)
    db.commit()
    logger.debug(f"Deleted booking: {booking_id}")
    return None

@router.post(
    "/optimize",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Optimize booking",
    description="Find and book the optimal room for a one-hour slot. Requires authentication."
)
def optimize_booking(
    booking: BookingOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Find and book the optimal room for a one-hour slot.
    Requires authentication.

    - **start_time**: Start time of the booking.
    - **required_capacity**: Required room capacity.
    - **purpose**: Purpose of the booking.

    Returns the created booking.
    """
    logger.debug(f"Optimizing booking for user: {current_user['username']}, start_time: {booking.start_time}, capacity: {booking.required_capacity}")

    # Validate start_time
    if booking.start_time.minute != 0 or booking.start_time.second != 0:
        logger.error(f"Invalid start_time: {booking.start_time}, must be at start of hour")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be at the start of an hour")

    # Calculate end_time
    end_time = booking.start_time + timedelta(hours=1)
    logger.debug(f"Calculated end_time: {end_time}")

    # Find optimal room
    optimal_room = find_optimal_room(db, booking.start_time, end_time, booking.required_capacity)
    if not optimal_room:
        logger.error(f"No suitable room available for start_time: {booking.start_time}, capacity: {booking.required_capacity}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No suitable room available")

    # Create booking
    db_booking = Booking(
        room_id=optimal_room.id,
        user_id=current_user["id"],
        start_time=booking.start_time,
        end_time=end_time,
        purpose=booking.purpose,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    logger.debug(f"Created optimized booking: {db_booking.id}, room_id: {optimal_room.id}, end_time: {db_booking.end_time}")
    return db_booking

@router.get(
    "/available_slots/",
    response_model=List[Dict[str, datetime]],
    summary="List available time slots",
    description="Retrieve available time slots for a room on a specific date. Requires authentication."
)
def get_available_slots(
    room_id: int,
    date: date,
    duration: int = 60,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List available time slots for a room.

    - **room_id**: ID of the room to check availability for.
    - **date**: Date to check availability (e.g., 2025-05-04).
    - **duration**: Duration of each slot in minutes (default: 60).

    Returns a list of available slots with start_time and end_time.
    """
    logger.debug(f"Fetching available slots for room_id: {room_id}, date: {date}, duration: {duration} minutes, user: {current_user['username']}")

    # Validate inputs
    if duration <= 0:
        logger.error(f"Invalid duration: {duration}, must be positive")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duration must be positive")

    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        logger.error(f"Room not found: {room_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Define the day's time range (8 AM to 6 PM)
    day_start = datetime.combine(date, datetime.min.time()) + timedelta(hours=8)
    day_end = day_start + timedelta(hours=10)  # 8 AM to 6 PM

    # Get existing bookings for the room on the date
    bookings = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.start_time >= day_start,
        Booking.end_time <= day_end
    ).order_by(Booking.start_time).all()

    # Initialize slots
    slots = []
    current_time = day_start
    duration_delta = timedelta(minutes=duration)

    # Handle bookings and find gaps
    for booking in bookings:
        # Add slots before the current booking
        while current_time + duration_delta <= booking.start_time:
            slot_end = current_time + duration_delta
            slots.append({"start_time": current_time, "end_time": slot_end})
            current_time = slot_end
        current_time = max(current_time, booking.end_time)

    # Add slots after the last booking
    while current_time + duration_delta <= day_end:
        slot_end = current_time + duration_delta
        slots.append({"start_time": current_time, "end_time": slot_end})
        current_time = slot_end

    logger.debug(f"Found {len(slots)} available slots for room_id: {room_id}")
    return slots
