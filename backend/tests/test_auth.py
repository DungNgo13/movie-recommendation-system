import pytest
import sys
import os
import uuid
import time
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt

# Add the parent directory (backend) to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.core import security

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
from sqlalchemy.pool import StaticPool

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_user(db_session: Session):
    password = "MySecurePassword123"
    user = User(
        email="testauth@example.com",
        password_hash=security.hash_password(password),
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


def test_login_success(test_user):
    user, password = test_user
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # decode the token to verify it uses user.id
    payload = jwt.decode(data["access_token"], security.SECRET_KEY, algorithms=[security.ALGORITHM])
    assert payload["sub"] == str(user.id)


def test_invalid_token(test_user):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_expired_token(test_user):
    user, _ = test_user
    # Create an artificially expired token
    to_encode = {"sub": str(user.id)}
    expire = datetime.now(timezone.utc) - timedelta(minutes=1)
    to_encode.update({"exp": expire})
    expired_token = jwt.encode(to_encode, security.SECRET_KEY, algorithm=security.ALGORITHM)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    # JWTError should happen, causing Invalid or expired
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_get_me_success(test_user):
    user, password = test_user
    
    # Get token via login
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password}
    )
    token = login_response.json()["access_token"]
    
    # Call /me
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    data = me_response.json()
    assert data["email"] == user.email
    assert data["id"] == str(user.id)
    assert data["role"] == user.role
