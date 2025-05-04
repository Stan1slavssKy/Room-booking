from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.room import Room
from app.models.booking import Booking

def find_optimal_room(db: Session, start_time: datetime, end_time: datetime, required_capacity: int):
    """
    Find the smallest available room that meets the capacity requirement for a one-hour slot.
    """
    # Validate start_time is at the start of an hour
    if start_time.minute != 0 or start_time.second != 0 or start_time.microsecond != 0:
        raise ValueError("Start time must be at the beginning of an hour (e.g., 13:00:00)")

    # Get all rooms with sufficient capacity
    available_rooms = db.query(Room).filter(Room.capacity >= required_capacity).all()
    
    # Check for conflicts
    optimal_room = None
    min_occupancy = float('inf')
    
    for room in available_rooms:
        conflicts = db.query(Booking).filter(
            Booking.room_id == room.id,
            Booking.start_time < end_time,
            Booking.start_time >= start_time - timedelta(hours=1)
        ).count()
        
        if conflicts == 0 and room.capacity < min_occupancy:
            optimal_room = room
            min_occupancy = room.capacity
    
    return optimal_room
