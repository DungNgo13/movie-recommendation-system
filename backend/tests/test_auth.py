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

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.pop(get_db, None)
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


# ──────────────────────────────────────────────────────────────────────
# Client IP extraction tests
# ──────────────────────────────────────────────────────────────────────

def test_login_records_forwarded_ip(test_user, db_session):
    """
    When X-Forwarded-For is set (reverse proxy), the first IP in the
    comma-separated list should be stored as last_login_ip.
    """
    user, password = test_user
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
        headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.1"},
    )
    assert response.status_code == 200

    db_session.refresh(user)
    assert user.last_login_ip == "203.0.113.50"


def test_login_records_real_ip(test_user, db_session):
    """
    When only X-Real-IP is set (no X-Forwarded-For), that value should be
    stored as last_login_ip.
    """
    user, password = test_user
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
        headers={"X-Real-IP": "198.51.100.7"},
    )
    assert response.status_code == 200

    db_session.refresh(user)
    assert user.last_login_ip == "198.51.100.7"


def test_login_rejects_spoofed_ip_header(test_user, db_session):
    """
    If X-Forwarded-For contains garbage (not a valid IP), the helper
    should fall back rather than storing arbitrary text.
    """
    user, password = test_user
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
        headers={"X-Forwarded-For": "not-an-ip; DROP TABLE users"},
    )
    assert response.status_code == 200

    db_session.refresh(user)
    # Should NOT contain the spoofed value
    assert user.last_login_ip != "not-an-ip; DROP TABLE users"


def test_login_fallback_to_client_host(test_user, db_session):
    """
    When no proxy headers are present, request.client.host (testclient)
    should be recorded.
    """
    user, password = test_user
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200

    db_session.refresh(user)
    # TestClient uses 'testclient' as the host
    assert user.last_login_ip is not None
    assert len(user.last_login_ip) > 0


# ──────────────────────────────────────────────────────────────────────
# Login tracking — last_login_at
# ──────────────────────────────────────────────────────────────────────

def test_login_updates_last_login_at(test_user, db_session):
    """
    A successful login should update last_login_at to a recent timestamp.
    """
    user, password = test_user
    assert user.last_login_at is None  # not set before first login

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200

    db_session.refresh(user)
    assert user.last_login_at is not None


# ──────────────────────────────────────────────────────────────────────
# Password reset flow
# ──────────────────────────────────────────────────────────────────────

def test_forgot_password_returns_generic_response(db_session):
    """
    /forgot-password should always return 200 with a generic message,
    regardless of whether the email exists. This prevents email enumeration.
    """
    # Non-existent email — must still return 200
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # Must NOT mention whether the email exists
    assert "not found" not in data["message"].lower()
    assert "doesn't exist" not in data["message"].lower()


def test_reset_password_with_valid_token(test_user, db_session):
    """
    A valid, non-expired reset token should allow the password to be changed.
    """
    user, password = test_user

    # Generate a reset token
    from app.services.auth_service import create_password_reset_token
    token = create_password_reset_token(db_session, user.email)
    assert token is not None

    new_password = "NewSecure123!"
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert response.status_code == 200

    # Token should be cleared (single-use)
    db_session.refresh(user)
    assert user.password_reset_token is None

    # Old password should no longer work
    login_old = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_old.status_code == 401

    # New password should work
    login_new = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": new_password},
    )
    assert login_new.status_code == 200


def test_reset_password_with_invalid_token(db_session):
    """
    An invalid or expired token should return 400.
    """
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "completely-invalid-token", "new_password": "NewSecure123!"},
    )
    assert response.status_code == 400


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────

def test_register_creates_user_and_triggers_welcome_email(db_session, monkeypatch):
    """
    POST /register should create the user, return 201, and trigger a
    welcome email call.
    """
    # Capture email calls without actually sending
    email_calls = []
    monkeypatch.setattr(
        "app.routers.auth.send_welcome_email",
        lambda email: email_calls.append(email),
    )

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "StrongPass1!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "user"

    # Verify the user exists in DB
    from app.models.user import User
    user = db_session.query(User).filter(User.email == "newuser@example.com").first()
    assert user is not None

    # Verify welcome email was triggered
    assert len(email_calls) == 1
    assert email_calls[0] == "newuser@example.com"

