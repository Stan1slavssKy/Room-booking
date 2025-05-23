from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.room import Room
from app.models.booking import Booking
from app.utils.validation_helpers import validate_start_time


def find_optimal_room(
    db: Session, start_time: datetime, end_time: datetime, required_capacity: int
):
    """
    Find the smallest available room that meets the capacity requirement for a one-hour slot.
    """
    # Validate start_time is at the start of an hour
    validate_start_time(start_time)

    # Get all rooms with sufficient capacity
    available_rooms = db.query(Room).filter(Room.capacity >= required_capacity).all()

    # Check for conflicts
    optimal_room = None
    min_occupancy = float("inf")

    for room in available_rooms:
        conflicts = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.start_time < end_time,
                Booking.start_time >= start_time - timedelta(hours=1),
            )
            .count()
        )

        if conflicts == 0 and room.capacity < min_occupancy:
            optimal_room = room
            min_occupancy = room.capacity

    return optimal_room
