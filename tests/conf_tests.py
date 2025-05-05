import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db
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
    """Clear all data from all tables after each test"""
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        trans.commit()


@pytest.fixture
def test_db():
    """Provide a database session for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_next_user():
    """Helper function to generate unique usernames"""
    if not hasattr(get_next_user, "user_count"):
        get_next_user.user_count = 0
    get_next_user.user_count += 1
    return get_next_user.user_count


@pytest.fixture
def test_user_data():
    """Fixture for test user data with unique username"""
    username = get_next_user()
    return {
        "username": f"user_{username}",
        "email": f"user_{username}@example.com",
        "password": "testpassword",
    }


@pytest.fixture
def test_user(test_db):
    """Fixture to create a test user in the database"""
    username = get_next_user()
    user_data = {
        "username": f"user_{username}",
        "email": f"user_{username}@example.com",
        "hashed_password": "testpassword",
    }

    db_user = test_db.query(User).filter(User.username == user_data["username"]).first()
    if not db_user:
        db_user = User(**user_data)
        test_db.add(db_user)
        test_db.commit()
        test_db.refresh(db_user)

    return db_user


@pytest.fixture
def auth_headers(test_db, test_user_data):
    """Fixture to get authentication headers"""
    # Create test user directly in database
    hashed_password = get_password_hash(test_user_data["password"])
    user = User(
        username=test_user_data["username"],
        email=test_user_data["email"],
        hashed_password=hashed_password,
    )
    test_db.add(user)
    test_db.commit()

    # Login to get access token
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"],
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
