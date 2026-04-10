"""
Tests for Phase 3 watch-progress endpoints and service logic.
Pattern mirrors test_auth.py / test_movies.py:
  - SQLite in-memory DB
  - TestClient with dependency override
  - per-function db_session fixture
"""
import pytest
import uuid
import sys
import os
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.movie import Movie
from app.models.watch_history import WatchHistory
from app.core import security

# ── Test DB setup ─────────────────────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
    """Create a regular user and return (user, auth_token)."""
    password = "TestPass123!"
    user = User(
        email=f"watcher_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=security.hash_password(password),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = resp.json()["access_token"]
    return user, token


@pytest.fixture(scope="function")
def test_movie(db_session: Session):
    """Create a single movie for watch-progress tests."""
    movie = Movie(
        id=uuid.uuid4(),
        title="Phase 3 Test Film",
        release_date=date(2020, 1, 1),
        genres=["Drama"],
        director="Test Director",
    )
    db_session.add(movie)
    db_session.commit()
    db_session.refresh(movie)
    return movie


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Helper ────────────────────────────────────────────────────────────────────

def save_progress(token: str, movie_id, current: int, duration: int, percent: float):
    return client.post(
        "/api/v1/watch-progress",
        json={
            "movie_id": str(movie_id),
            "current_time_seconds": current,
            "duration_seconds": duration,
            "progress_percent": percent,
        },
        headers=auth_headers(token),
    )


# ── 1. Save watch progress — success ─────────────────────────────────────────

def test_save_watch_progress_success(db_session, test_user, test_movie):
    _, token = test_user

    resp = save_progress(token, test_movie.id, 120, 1800, 6.7)

    assert resp.status_code == 200
    data = resp.json()
    assert data["movie_id"] == str(test_movie.id)
    assert data["current_time_seconds"] == 120
    assert data["duration_seconds"] == 1800
    assert data["is_completed"] is False


def test_save_watch_progress_updates_existing(db_session, test_user, test_movie):
    """Saving twice for the same movie should upsert, not duplicate."""
    _, token = test_user

    save_progress(token, test_movie.id, 60, 1800, 3.3)
    resp = save_progress(token, test_movie.id, 300, 1800, 16.7)

    assert resp.status_code == 200
    assert resp.json()["current_time_seconds"] == 300

    # Only one DB row should exist
    rows = db_session.query(WatchHistory).filter(
        WatchHistory.movie_id == test_movie.id
    ).all()
    assert len(rows) == 1


# ── 2. Get watch progress — success ──────────────────────────────────────────

def test_get_watch_progress_success(db_session, test_user, test_movie):
    _, token = test_user

    save_progress(token, test_movie.id, 200, 1800, 11.1)

    resp = client.get(
        f"/api/v1/watch-progress/{test_movie.id}",
        headers=auth_headers(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["current_time_seconds"] == 200
    assert data["is_completed"] is False


def test_get_watch_progress_no_record_returns_zero(db_session, test_user, test_movie):
    """No prior watch → endpoint should return zeros gracefully, not 404."""
    _, token = test_user

    resp = client.get(
        f"/api/v1/watch-progress/{test_movie.id}",
        headers=auth_headers(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["current_time_seconds"] == 0
    assert data["is_completed"] is False


# ── 3. Unauthorized requests rejected ────────────────────────────────────────

def test_save_progress_without_token_is_rejected(db_session, test_movie):
    resp = client.post(
        "/api/v1/watch-progress",
        json={
            "movie_id": str(test_movie.id),
            "current_time_seconds": 60,
            "duration_seconds": 1800,
            "progress_percent": 3.3,
        },
    )
    assert resp.status_code == 401


def test_get_progress_without_token_is_rejected(db_session, test_movie):
    resp = client.get(f"/api/v1/watch-progress/{test_movie.id}")
    assert resp.status_code == 401


def test_save_progress_invalid_movie_id_rejected(db_session, test_user):
    _, token = test_user

    resp = client.post(
        "/api/v1/watch-progress",
        json={
            "movie_id": "not-a-uuid",
            "current_time_seconds": 60,
            "duration_seconds": 1800,
            "progress_percent": 3.3,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


# ── 4. Completed movie handling ───────────────────────────────────────────────

def test_movie_marked_completed_at_95_percent(db_session, test_user, test_movie):
    _, token = test_user

    save_progress(token, test_movie.id, 1710, 1800, 95.0)

    resp = client.get(
        f"/api/v1/watch-progress/{test_movie.id}",
        headers=auth_headers(token),
    )
    data = resp.json()
    assert data["is_completed"] is True


def test_completed_movie_resume_position_is_zero(db_session, test_user, test_movie):
    """A completed movie should return current_time_seconds=0 so it replays from start."""
    _, token = test_user

    save_progress(token, test_movie.id, 1800, 1800, 100.0)

    resp = client.get(
        f"/api/v1/watch-progress/{test_movie.id}",
        headers=auth_headers(token),
    )
    data = resp.json()
    assert data["is_completed"] is True
    assert data["current_time_seconds"] == 0


def test_below_95_percent_not_marked_completed(db_session, test_user, test_movie):
    _, token = test_user

    save_progress(token, test_movie.id, 1600, 1800, 88.9)

    resp = client.get(
        f"/api/v1/watch-progress/{test_movie.id}",
        headers=auth_headers(token),
    )
    data = resp.json()
    assert data["is_completed"] is False
    assert data["current_time_seconds"] == 1600


# ── 5. Continue watching — history list ──────────────────────────────────────

def test_history_me_returns_unfinished_items(db_session, test_user, test_movie):
    """POST to /history/{id} then GET /history/me should include the movie."""
    _, token = test_user

    client.post(
        f"/api/v1/history/{test_movie.id}",
        json={"playback_position_seconds": 120},
        headers=auth_headers(token),
    )

    resp = client.get("/api/v1/history/me?limit=10", headers=auth_headers(token))

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == str(test_movie.id)
    assert items[0]["title"] == test_movie.title


def test_history_me_includes_progress_fields(db_session, test_user, test_movie):
    """History list should return progress_percent and is_completed."""
    _, token = test_user

    save_progress(token, test_movie.id, 300, 1800, 16.7)

    resp = client.get("/api/v1/history/me?limit=10", headers=auth_headers(token))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert "progress_percent" in item
    assert "is_completed" in item
    assert item["is_completed"] is False


def test_history_me_without_token_rejected(db_session):
    resp = client.get("/api/v1/history/me?limit=5")
    assert resp.status_code == 401


def test_history_me_route_not_confused_with_movie_id(db_session, test_user):
    """Regression: /history/me must NOT match /{movie_id} and return 422."""
    _, token = test_user
    resp = client.get("/api/v1/history/me", headers=auth_headers(token))
    # Should succeed (200), not 422
    assert resp.status_code == 200


def test_multiple_movies_ordered_by_most_recent(db_session, test_user):
    """History should return most recently watched first."""
    _, token = test_user

    movie_a = Movie(id=uuid.uuid4(), title="Movie A", genres=["Action"], director="Dir A")
    movie_b = Movie(id=uuid.uuid4(), title="Movie B", genres=["Drama"], director="Dir B")
    db_session.add_all([movie_a, movie_b])
    db_session.commit()

    # Watch A, then B — B should appear first
    client.post(
        f"/api/v1/history/{movie_a.id}",
        json={"playback_position_seconds": 60},
        headers=auth_headers(token),
    )
    client.post(
        f"/api/v1/history/{movie_b.id}",
        json={"playback_position_seconds": 60},
        headers=auth_headers(token),
    )

    resp = client.get("/api/v1/history/me?limit=10", headers=auth_headers(token))
    items = resp.json()
    assert items[0]["title"] == "Movie B"
    assert items[1]["title"] == "Movie A"
