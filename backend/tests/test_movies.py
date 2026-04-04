import pytest
import uuid
import sys
import os
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add the parent directory (backend) to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import Base, get_db
from app.models import movie as movie_model

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
    """
    Fixture to create and teardown the database for each test function.
    """
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
def seed_movies(db_session: Session):
    """
    Fixture to seed the database with mock movie data.
    """
    movies_data = [
        movie_model.Movie(
            id=uuid.uuid4(), title="Inception", release_date=date(2010, 7, 16),
            genres=["Action", "Sci-Fi"], director="Christopher Nolan"
        ),
        movie_model.Movie(
            id=uuid.uuid4(), title="The Matrix", release_date=date(1999, 3, 31),
            genres=["Action", "Sci-Fi"], director="Wachowskis"
        ),
        movie_model.Movie(
            id=uuid.uuid4(), title="Parasite", release_date=date(2019, 5, 30),
            genres=["Thriller", "Comedy"], director="Bong Joon Ho"
        ),
    ]
    db_session.add_all(movies_data)
    db_session.commit()
    return movies_data


def test_read_movies_paginated(seed_movies):
    """
    Tests the paginated movie list endpoint.
    """
    response = client.get("/api/v1/movies/?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["limit"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Inception"
    assert data["items"][0]["release_year"] == 2010

def test_read_movie_detail(seed_movies):
    """
    Tests the movie detail endpoint with a valid UUID.
    """
    movie_id = str(seed_movies[0].id)
    response = client.get(f"/api/v1/movies/{movie_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Inception"
    assert data["id"] == movie_id
    assert data["director"] == "Christopher Nolan"
    assert data["genres"] == ["Action", "Sci-Fi"]

def test_read_movie_detail_not_found(db_session: Session):
    """
    Tests the movie detail endpoint with a non-existent UUID.
    """
    non_existent_id = uuid.uuid4()
    response = client.get(f"/api/v1/movies/{non_existent_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found"}

from app.routers.auth import get_current_admin_user
from app.models.user import User

def override_get_current_admin_user():
    return User(id=uuid.uuid4(), email="admin@test.com", role="admin")

def test_upload_poster_success(seed_movies):
    """
    Tests successful poster image upload.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    files = {"file": ("test_poster.jpg", b"fake image bytes", "image/jpeg")}
    
    response = client.post(f"/api/v1/movies/{movie_id}/poster", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "media/images/posters" in data["poster_url"]
    assert data["poster_url"].endswith(".jpg")

def test_upload_backdrop_success(seed_movies):
    """
    Tests successful backdrop image upload.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    files = {"file": ("test_bg.png", b"fake image bytes", "image/png")}
    
    response = client.post(f"/api/v1/movies/{movie_id}/backdrop", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "media/images/backdrops" in data["backdrop_url"]
    assert data["backdrop_url"].endswith(".png")

def test_upload_invalid_file_type(seed_movies):
    """
    Tests upload rejection for invalid formats (e.g. text/plain).
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    files = {"file": ("test.txt", b"text bytes", "text/plain")}
    
    response = client.post(f"/api/v1/movies/{movie_id}/poster", files=files)
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

def test_upload_video_success(seed_movies):
    """
    Tests successful mp4 video upload.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    files = {"file": ("test_vid.mp4", b"fake video bytes", "video/mp4")}
    
    with patch("subprocess.run") as mock_run:
        response = client.post(f"/api/v1/movies/{movie_id}/video", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "media/videos/source" in data["video_url"]
        assert data["video_url"].endswith(".mp4")
        assert data["video_status"] == "uploaded"

def test_upload_video_invalid_type(seed_movies):
    """
    Tests upload rejection for invalid formats (e.g. video/x-matroska or text/plain).
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    files = {"file": ("test.mkv", b"mkv bytes", "video/x-matroska")}
    
    response = client.post(f"/api/v1/movies/{movie_id}/video", files=files)
    
    assert response.status_code == 400
    assert "Invalid file type. Only MP4 allowed." in response.json()["detail"]

from unittest.mock import patch

def test_trigger_hls_conversion(seed_movies, db_session):
    """
    Tests triggering background HLS conversion correctly.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)
    
    # Needs "uploaded" state to trigger
    movie = db_session.query(movie_model.Movie).filter_by(id=seed_movies[0].id).first()
    movie.processing_status = "uploaded"
    movie.video_source_path = "media/videos/source/fake.mp4"
    db_session.commit()
    
    with patch("subprocess.run") as mock_run:
        response = client.post(f"/api/v1/movies/{movie_id}/process-hls")
        assert response.status_code == 202
        assert response.json() == {"message": "HLS conversion started in the background."}
        
def test_get_hls_status(seed_movies, db_session):
    """
    Tests fetching correct HLS processing states.
    """
    movie_id = str(seed_movies[0].id)
    
    movie = db_session.query(movie_model.Movie).filter_by(id=seed_movies[0].id).first()
    movie.processing_status = "ready"
    movie.hls_playlist_path = "media/videos/hls/fake_play.m3u8"
    db_session.commit()
    
    response = client.get(f"/api/v1/movies/{movie_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["video_status"] == "ready"
        
def test_create_movie_year_only(db_session, seed_movies):
    """
    Tests creating a movie passing only 'YYYY' as release_date.
    The schema should pad it securely so the Date column continues to function.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    payload = {
        "title": "Dune: Part Two",
        "release_date": "2024",
    }
    response = client.post("/api/v1/movies/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Dune: Part Two"
    assert data["release_date"] == "2024-01-01"
    
def test_create_movie_invalid_year(db_session, seed_movies):
    """
    Tests creating a movie passing an invalid string for release_date.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    payload = {
        "title": "Invalid Year Movie",
        "release_date": "NotAYear",
    }
    response = client.post("/api/v1/movies/", json=payload)
    assert response.status_code == 422
    assert "Release date must be 'YYYY' or 'YYYY-MM-DD'" in str(response.json())
