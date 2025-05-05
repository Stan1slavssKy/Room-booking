import pytest
from fastapi import status
from app.models.room import Room
from tests.conf_tests import client, clear_db, test_user_data, test_db, auth_headers


@pytest.fixture
def test_room(test_db):
    room = Room(name="Conference Room A", capacity=10, location="Floor 1")
    test_db.add(room)
    test_db.commit()
    test_db.refresh(room)
    return room


# Tests
def test_create_room_unauthorized():
    response = client.post(
        "/rooms/", json={"name": "Meeting Room", "capacity": 5, "location": "Floor 2"}
    )
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]


def test_create_room_success(auth_headers):
    room_data = {"name": "Meeting Room", "capacity": 5, "location": "Floor 2"}
    response = client.post("/rooms/", json=room_data, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED


def test_get_rooms_with_data(test_room):
    response = client.get("/rooms/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_room.id
    assert data[0]["name"] == test_room.name


def test_get_room_success(test_room):
    response = client.get(f"/rooms/{test_room.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_room.id
    assert data["capacity"] == test_room.capacity
    assert data["location"] == test_room.location


def test_get_room_not_found():
    response = client.get("/rooms/9999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Room not found"


def test_update_room_unauthorized(test_room):
    response = client.put(f"/rooms/{test_room.id}", json={"name": "Updated Name"})
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]


def test_update_room_success(auth_headers, test_room):
    update_data = {
        "name": "Updated Conference Room",
        "capacity": 15,
        "location": "Floor 3",
    }
    response = client.put(
        f"/rooms/{test_room.id}", json=update_data, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["capacity"] == update_data["capacity"]
    assert data["location"] == update_data["location"]


def test_partial_update_room(auth_headers, test_room):
    update_data = {"capacity": 20}
    response = client.put(
        f"/rooms/{test_room.id}", json=update_data, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["capacity"] == 20
    assert data["name"] == test_room.name
    assert data["location"] == test_room.location


def test_update_room_not_found(auth_headers):
    response = client.put(
        "/rooms/9999", json={"name": "Non-existent Room"}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_room_unauthorized(test_room):
    response = client.delete(f"/rooms/{test_room.id}")
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]


def test_delete_room_success(auth_headers, test_room, test_db):
    response = client.delete(f"/rooms/{test_room.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    deleted_room = test_db.query(Room).filter(Room.id == test_room.id).first()
    assert deleted_room is None


def test_delete_room_not_found(auth_headers):
    response = client.delete("/rooms/9999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
