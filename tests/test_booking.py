# tests/test_bookings.py
import pytest
from datetime import datetime, timedelta, date
from fastapi import status
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingOptimizeRequest,
)

from tests.conf_tests import client, clear_db, test_db, test_user_data, test_user, auth_headers

# Test data
TEST_ROOM_DATA = {
    "name": "Test Room",
    "capacity": 10,
    "location": "Floor 1"
}

TEST_BOOKING_DATA = Booking(
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2),
    purpose="Team Meeting",
)

TEST_OPTIMIZE_DATA = {
    "start_time": (datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)).isoformat(),
    "end_time": (datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=3)).isoformat(),
    "purpose": "Optimized Meeting",
    "required_capacity": 5
}

# Fixtures
@pytest.fixture
def test_room(test_db):
    room = Room(**TEST_ROOM_DATA)
    test_db.add(room)
    test_db.commit()
    test_db.refresh(room)
    return room

@pytest.fixture
def test_booking(test_db, test_room, test_user):
    booking = Booking(
        room_id=test_room.id,
        user_id=test_user.id,
        start_time=TEST_BOOKING_DATA.start_time,
        end_time=TEST_BOOKING_DATA.end_time,
        purpose=TEST_BOOKING_DATA.purpose
    )
    test_db.add(booking)
    test_db.commit()
    test_db.refresh(booking)
    return booking


# Tests
def test_create_booking_success(auth_headers, test_room):
    booking_data = {**TEST_BOOKING_DATA, "room_id": test_room.id}
    print(booking_data)
    print("_____")
    response = client.post(
        "/bookings/",
        json=booking_data,
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["room_id"] == test_room.id
    assert data["purpose"] == TEST_BOOKING_DATA["purpose"]
    assert data["start_time"] == TEST_BOOKING_DATA["start_time"]

def test_create_booking_unauthorized(test_room):
    booking_data = {**TEST_BOOKING_DATA, "room_id": test_room.id}
    response = client.post("/bookings/", json=booking_data)
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

# def test_create_booking_invalid_time(auth_headers, test_room):
#     invalid_time = datetime.now().replace(minute=30)
#     booking_data = {
#         **TEST_BOOKING_DATA,
#         "room_id": test_room.id,
#         "start_time": invalid_time.isoformat()
#     }
#     response = client.post("/bookings/", json=booking_data, headers=auth_headers)
#     assert response.status_code == status.HTTP_400_BAD_REQUEST
#     assert "start of an hour" in response.json()["detail"]

def test_create_booking_room_not_found(auth_headers):
    booking_data = {**TEST_BOOKING_DATA, "room_id": 999}
    response = client.post("/bookings/", json=booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_create_booking_insufficient_capacity(auth_headers, test_room):
    booking_data = {
        **TEST_BOOKING_DATA,
        "room_id": test_room.id,
        "required_capacity": 20  # More than test room capacity
    }
    response = client.post("/bookings/", json=booking_data, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "capacity insufficient" in response.json()["detail"]

# def test_create_booking_overlapping(auth_headers, test_room, test_booking):
#     booking_data = {
#         **TEST_BOOKING_DATA,
#         "room_id": test_room.id,
#         "start_time": test_booking.start_time  # Same time as existing booking
#     }
#     response = client.post("/bookings/", json=booking_data, headers=auth_headers)
#     assert response.status_code == status.HTTP_400_BAD_REQUEST
#     assert "already booked" in response.json()["detail"]

def test_get_bookings(test_booking):
    response = client.get("/bookings/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_booking.id

# def test_get_booking(test_booking):
#     response = client.get(f"/bookings/{test_booking.id}")
#     assert response.status_code == status.HTTP_200_OK
#     data = response.json()
#     assert data["id"] == test_booking.id

# def test_get_booking_not_found(client):
#     response = client.get("/bookings/999")
#     assert response.status_code == status.HTTP_404_NOT_FOUND

# def test_update_booking_success(auth_headers, test_booking):
#     update_data = {
#         "purpose": "Updated Meeting",
#         "start_time": (test_booking.start_time + timedelta(hours=2)).isoformat()
#     }
#     response = client.put(
#         f"/bookings/{test_booking.id}",
#         json=update_data,
#         headers=auth_headers
#     )
#     assert response.status_code == status.HTTP_200_OK
#     data = response.json()
#     assert data["purpose"] == "Updated Meeting"

# def test_update_booking_unauthorized(test_booking):
#     response = client.put(
#         f"/bookings/{test_booking.id}",
#         json={"purpose": "Should Fail"}
#     )
#     assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

# def test_update_booking_not_owner(auth_headers, test_db):
#     # Create another user and booking
#     other_user = User(username="other", email="other@test.com", hashed_password="hashed")
#     test_db.add(other_user)
#     test_db.commit()
    
#     other_booking = Booking(
#         room_id=1,
#         user_id=other_user.id,
#         start_time=TEST_BOOKING_DATA["start_time"] + timedelta(days=1),
#         end_time=TEST_BOOKING_DATA["start_time"] + timedelta(days=1, hours=1),
#         purpose="Other Booking"
#     )
#     test_db.add(other_booking)
#     test_db.commit()
    
#     response = client.put(
#         f"/bookings/{other_booking.id}",
#         json={"purpose": "Should Fail"},
#         headers=auth_headers
#     )
#     assert response.status_code == status.HTTP_403_FORBIDDEN

# def test_delete_booking_success(auth_headers, test_booking, test_db):
#     response = client.delete(
#         f"/bookings/{test_booking.id}",
#         headers=auth_headers
#     )
#     assert response.status_code == status.HTTP_204_NO_CONTENT
#     assert test_db.query(Booking).filter(Booking.id == test_booking.id).first() is None

# def test_optimize_booking_success(auth_headers, test_room):
#     response = client.post(
#         "/bookings/optimize",
#         json=TEST_OPTIMIZE_DATA,
#         headers=auth_headers
#     )
#     assert response.status_code == status.HTTP_201_CREATED
#     data = response.json()
#     assert data["room_id"] == test_room.id
#     assert data["purpose"] == TEST_OPTIMIZE_DATA["purpose"]

# def test_get_available_slots(auth_headers, test_room):
#     test_date = date.today()
#     response = client.get(
#         f"/bookings/available_slots/?room_id={test_room.id}&date={test_date}",
#         headers=auth_headers
#     )
#     assert response.status_code == status.HTTP_200_OK
#     slots = response.json()
#     assert isinstance(slots, list)
#     if slots:  # Might be empty if all slots are booked
#         assert "start_time" in slots[0]
#         assert "end_time" in slots[0]
