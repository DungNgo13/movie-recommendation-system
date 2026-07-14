import pytest
import sys
import os
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.movie import Movie
from app.core import security

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

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
    password = "MySecurePassword123!"
    user = User(
        email="favtest@example.com",
        password_hash=security.hash_password(password),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture(scope="function")
def auth_token(test_user):
    user, password = test_user
    resp = client.post("/api/v1/auth/login", json={
        "email": user.email,
        "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def sample_movies(db_session: Session):
    """Create 3 sample movies and return their IDs."""
    movies = []
    for i in range(3):
        movie = Movie(title=f"Test Movie {i + 1}")
        db_session.add(movie)
        db_session.commit()
        db_session.refresh(movie)
        movies.append(movie)
    return [str(m.id) for m in movies]


# ─── merge_guest_favorites service tests ─────────────────────────────────────


class TestMergeGuestFavoritesService:
    """Unit tests for favorite_service.merge_guest_favorites()."""

    def test_merge_empty_list(self, db_session, test_user):
        from app.services.favorite_service import merge_guest_favorites

        user, _ = test_user
        result = merge_guest_favorites(db_session, user.id, [])
        assert result == 0

    def test_merge_valid_movie_ids(self, db_session, test_user, sample_movies):
        from app.services.favorite_service import merge_guest_favorites, get_user_favorite_ids

        user, _ = test_user
        result = merge_guest_favorites(db_session, user.id, sample_movies)
        assert result == 3

        fav_ids = get_user_favorite_ids(db_session, user.id)
        assert set(fav_ids) == set(sample_movies)

    def test_merge_skips_duplicates(self, db_session, test_user, sample_movies):
        from app.services.favorite_service import merge_guest_favorites, add_favorite

        user, _ = test_user
        # Pre-add the first movie
        add_favorite(db_session, user.id, uuid.UUID(sample_movies[0]))

        # Merge all 3 — first should be skipped
        result = merge_guest_favorites(db_session, user.id, sample_movies)
        assert result == 2

    def test_merge_skips_invalid_uuids(self, db_session, test_user):
        from app.services.favorite_service import merge_guest_favorites

        user, _ = test_user
        result = merge_guest_favorites(db_session, user.id, [
            "not-a-uuid",
            "12345",
            "",
        ])
        assert result == 0

    def test_merge_mixed_valid_and_invalid(self, db_session, test_user, sample_movies):
        from app.services.favorite_service import merge_guest_favorites

        user, _ = test_user
        mixed = [sample_movies[0], "invalid-id", sample_movies[1]]
        result = merge_guest_favorites(db_session, user.id, mixed)
        assert result == 2


# ─── POST /me/merge endpoint tests ──────────────────────────────────────────


class TestMergeEndpoint:
    """Integration tests for POST /api/v1/favorites/me/merge."""

    def test_merge_unauthenticated(self, db_session):
        resp = client.post("/api/v1/favorites/me/merge", json={"movie_ids": []})
        assert resp.status_code == 401

    def test_merge_empty_list(self, auth_token, db_session):
        resp = client.post(
            "/api/v1/favorites/me/merge",
            json={"movie_ids": []},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["merged"] == 0

    def test_merge_valid_ids(self, auth_token, sample_movies, db_session):
        resp = client.post(
            "/api/v1/favorites/me/merge",
            json={"movie_ids": sample_movies},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["merged"] == 3

        # Verify via GET /me/ids
        ids_resp = client.get(
            "/api/v1/favorites/me/ids",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert ids_resp.status_code == 200
        assert set(ids_resp.json()) == set(sample_movies)

    def test_merge_skips_invalid_uuids(self, auth_token, db_session):
        resp = client.post(
            "/api/v1/favorites/me/merge",
            json={"movie_ids": ["not-a-uuid", "also-bad"]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["merged"] == 0

    def test_merge_idempotent(self, auth_token, sample_movies, db_session):
        """Merging the same IDs twice should not create duplicates."""
        client.post(
            "/api/v1/favorites/me/merge",
            json={"movie_ids": sample_movies},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = client.post(
            "/api/v1/favorites/me/merge",
            json={"movie_ids": sample_movies},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["merged"] == 0  # All already exist
