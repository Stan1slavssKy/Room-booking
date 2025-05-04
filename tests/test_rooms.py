import os
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db
from app.models.room import Room
from app.models.user import User
from app.utils.auth import get_password_hash

# Test database setup
if not os.path.exists("./out"):
    os.makedirs("./out")

SQLALCHEMY_DATABASE_URL = "sqlite:///./out/tests.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test tables
Base.metadata.create_all(bind=engine)


# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# Fixtures
@pytest.fixture(autouse=True)
def clear_db():
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        trans.commit()


@pytest.fixture
def test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_next_user():
    if not hasattr(get_next_user, "user_count"):
        get_next_user.user_count = 0
    get_next_user.user_count += 1
    return get_next_user.user_count


@pytest.fixture
def test_user_data():
    username = get_next_user()
    return {
        "username": f"{username}",
        "email": "testuser@example.com",
        "password": "testpassword",
    }


@pytest.fixture
def test_room(test_db):
    room = Room(name="Conference Room A", capacity=10, location="Floor 1")
    test_db.add(room)
    test_db.commit()
    test_db.refresh(room)
    return room


@pytest.fixture
def auth_headers(test_user_data):
    userinfo = test_user_data

    # First register the test user
    register_response = client.post(
        "/auth/register",
        json={
            "username": userinfo["username"],
            "email": userinfo["email"],
            "password": userinfo["password"],
        },
    )
    assert register_response.status_code == status.HTTP_201_CREATED

    # Then login to get the token
    login_response = client.post(
        "/auth/login",
        data={"username": userinfo["username"], "password": userinfo["password"]},
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
