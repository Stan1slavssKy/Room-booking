import pytest
from datetime import datetime, timedelta, date
from fastapi import status
from sqlalchemy.orm import Session
from sqlalchemy import String, DateTime
from dataclasses import dataclass

from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingOptimizeRequest,
)

from tests.conf_tests import (
    client,
    clear_db,
    test_db,
    test_user_data,
    test_user,
    auth_headers,
)

# Test data
TEST_ROOM_DATA = {"name": "Test Room", "capacity": 10, "location": "Floor 1"}


@dataclass
class BookingInfo:
    start_time: DateTime
    end_time: DateTime
    purpose: String
    required_capacity: int


TEST_BOOKING_DATA = BookingInfo(
    start_time=datetime.now().replace(minute=0, second=0, microsecond=0)
    + timedelta(hours=1),
    end_time=datetime.now().replace(minute=0, second=0, microsecond=0)
    + timedelta(hours=2),
    purpose="Team Meeting",
    required_capacity=9,
)

TEST_OPTIMIZE_DATA = BookingInfo(
    start_time=datetime.now().replace(minute=0, second=0, microsecond=0)
    + timedelta(hours=2),
    end_time=datetime.now().replace(minute=0, second=0, microsecond=0)
    + timedelta(hours=3),
    purpose="Optimized Meeting",
    required_capacity=5,
)


# Fixtures
@pytest.fixture
def test_room(test_db): # pylint: disable=redefined-outer-name
    room = Room(**TEST_ROOM_DATA)
    test_db.add(room)
    test_db.commit()
    test_db.refresh(room)
    return room


@pytest.fixture
def test_booking(test_db, test_room, test_user): # pylint: disable=redefined-outer-name
    booking = Booking(
        room_id=test_room.id,
        user_id=test_user.id,
        start_time=TEST_BOOKING_DATA.start_time,
        end_time=TEST_BOOKING_DATA.end_time,
        purpose=TEST_BOOKING_DATA.purpose,
    )
    test_db.add(booking)
    test_db.commit()
    test_db.refresh(booking)
    return booking


# Tests
# pylint: disable-next=redefined-outer-name
def test_create_booking_success(auth_headers, test_room):
    create_booking_data = {
        "room_id": test_room.id,
        "start_time": TEST_BOOKING_DATA.start_time.isoformat(),
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": TEST_BOOKING_DATA.required_capacity,
    }
    response = client.post("/bookings/", json=create_booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["room_id"] == test_room.id
    assert data["purpose"] == TEST_BOOKING_DATA.purpose
    assert data["start_time"] == TEST_BOOKING_DATA.start_time.isoformat()


# pylint: disable-next=redefined-outer-name
def test_create_booking_unauthorized(test_room):
    create_booking_data = {
        "room_id": test_room.id,
        "start_time": TEST_BOOKING_DATA.start_time.isoformat(),
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": TEST_BOOKING_DATA.required_capacity,
    }
    response = client.post("/bookings/", json=create_booking_data)
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]

# pylint: disable-next=redefined-outer-name
def test_create_booking_invalid_time(auth_headers, test_room):
    create_booking_data = {
        "room_id": test_room.id,
        "start_time": datetime.now()
        .replace(minute=1, second=1, microsecond=1)
        .isoformat(),
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": TEST_BOOKING_DATA.required_capacity,
    }
    response = client.post("/bookings/", json=create_booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Start time must be at the beginning of an hour (e.g., 13:00:00)"
        in response.json()["detail"]
    )

# pylint: disable-next=redefined-outer-name
def test_create_booking_room_not_found(auth_headers):
    create_booking_data = {
        "room_id": 999,
        "start_time": TEST_BOOKING_DATA.start_time.isoformat(),
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": TEST_BOOKING_DATA.required_capacity,
    }
    response = client.post("/bookings/", json=create_booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# pylint: disable-next=redefined-outer-name
def test_create_booking_insufficient_capacity(auth_headers, test_room):
    create_booking_data = {
        "room_id": test_room.id,
        "start_time": TEST_BOOKING_DATA.start_time.isoformat(),
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": 20,  # More than test room capacity
    }
    response = client.post("/bookings/", json=create_booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "capacity insufficient" in response.json()["detail"]

# pylint: disable-next=redefined-outer-name
def test_create_booking_overlapping(auth_headers, test_room, test_booking):
    create_booking_data = {
        "room_id": test_room.id,
        "start_time": test_booking.start_time.isoformat(),  # Same time as existing booking
        "purpose": TEST_BOOKING_DATA.purpose,
        "required_capacity": TEST_BOOKING_DATA.required_capacity,
    }
    response = client.post("/bookings/", json=create_booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already booked" in response.json()["detail"]

# pylint: disable-next=redefined-outer-name
def test_get_bookings(test_booking):
    response = client.get("/bookings/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_booking.id

# pylint: disable-next=redefined-outer-name
def test_get_booking(test_booking):
    response = client.get(f"/bookings/{test_booking.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_booking.id


def test_get_booking_not_found():
    response = client.get("/bookings/999")
    assert response.status_code == status.HTTP_404_NOT_FOUND

# pylint: disable-next=redefined-outer-name
def test_update_booking_unauthorized(test_booking):
    response = client.put(
        f"/bookings/{test_booking.id}", json={"purpose": "Should Fail"}
    )
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]

# pylint: disable-next=redefined-outer-name
def test_optimize_booking_success(auth_headers, test_room):
    optimize_request = {
        "room_id": test_room.id,
        "start_time": TEST_OPTIMIZE_DATA.start_time.isoformat(),
        "purpose": TEST_OPTIMIZE_DATA.purpose,
        "required_capacity": TEST_OPTIMIZE_DATA.required_capacity,
    }
    response = client.post(
        "/bookings/optimize", json=optimize_request, headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["room_id"] == test_room.id
    assert data["purpose"] == TEST_OPTIMIZE_DATA.purpose

# pylint: disable-next=redefined-outer-name
def test_get_available_slots(auth_headers, test_room):
    test_date = date.today()
    response = client.get(
        f"/bookings/available_slots/?room_id={test_room.id}&date={test_date}",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    slots = response.json()
    assert isinstance(slots, list)
    if slots:
        assert "start_time" in slots[0]
        assert "end_time" in slots[0]
