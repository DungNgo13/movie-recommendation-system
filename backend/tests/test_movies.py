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
    MKV and other video/* formats are now accepted (returns 200).
    Only genuinely non-video MIME types (e.g. text/plain) are rejected with 400.
    """
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    movie_id = str(seed_movies[0].id)

    # MKV must now succeed
    files = {"file": ("test.mkv", b"mkv bytes", "video/x-matroska")}
    response = client.post(f"/api/v1/movies/{movie_id}/video", files=files)
    assert response.status_code == 200

    # A non-video type must still be rejected
    files_bad = {"file": ("malicious.txt", b"text bytes", "text/plain")}
    response_bad = client.post(f"/api/v1/movies/{movie_id}/video", files=files_bad)
    assert response_bad.status_code == 400
    assert "video files are allowed" in response_bad.json()["detail"]

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
        assert response.json()["message"] == "HLS conversion queued successfully."
        
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


# ──────────────────────────────────────────────────────────────────────
# Server-side search & filter tests
# ──────────────────────────────────────────────────────────────────────

def test_search_movies_by_title(seed_movies):
    """
    GET /api/v1/movies?search=incep → returns only 'Inception' (partial, case-insensitive).
    """
    response = client.get("/api/v1/movies?search=incep")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Inception"


def test_search_movies_case_insensitive(seed_movies):
    """
    Search is case-insensitive: 'MATRIX' should find 'The Matrix'.
    """
    response = client.get("/api/v1/movies?search=MATRIX")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "The Matrix"


def test_filter_movies_by_year(seed_movies):
    """
    GET /api/v1/movies?year=2019 → only 'Parasite'.
    """
    response = client.get("/api/v1/movies?year=2019")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Parasite"


def test_filter_movies_by_genre(seed_movies):
    """
    GET /api/v1/movies?genre=Comedy → only 'Parasite' (genres: Thriller, Comedy).
    """
    response = client.get("/api/v1/movies?genre=Comedy")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Parasite"


def test_filter_movies_by_genre_shared(seed_movies):
    """
    GET /api/v1/movies?genre=Action → 'Inception' and 'The Matrix' (both have Action).
    """
    response = client.get("/api/v1/movies?genre=Action")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Inception", "The Matrix"}


def test_filter_movies_combined(seed_movies):
    """
    Combine search + genre + year: only Inception matches all three.
    """
    response = client.get("/api/v1/movies?search=in&genre=Sci-Fi&year=2010")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Inception"


def test_filter_movies_no_results(seed_movies):
    """
    Filters that match nothing should return total=0 and empty items.
    """
    response = client.get("/api/v1/movies?search=nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


# ─── Quality Ladder Tests ────────────────────────────────────────────────────

from app.services.hls_service import select_hls_qualities


class TestSelectHlsQualities:
    """Unit tests for the HLS quality-ladder selection helper."""

    def _labels(self, source_height: int) -> list[str]:
        """Helper: return quality labels for a given source height."""
        return [f"{h}p" for _, h, _ in select_hls_qualities(source_height)]

    def test_4k_source_includes_all_tiers(self):
        """2160p source should generate all 6 quality tiers."""
        labels = self._labels(2160)
        assert labels == ["360p", "480p", "720p", "1080p", "1440p", "2160p"]

    def test_1440p_source_excludes_2160p(self):
        """1440p source should include up to 1440p but not 2160p."""
        labels = self._labels(1440)
        assert "1440p" in labels
        assert "2160p" not in labels
        assert labels == ["360p", "480p", "720p", "1080p", "1440p"]

    def test_1080p_source_excludes_1440p_and_2160p(self):
        """1080p source should include up to 1080p."""
        labels = self._labels(1080)
        assert "1080p" in labels
        assert "1440p" not in labels
        assert "2160p" not in labels
        assert labels == ["360p", "480p", "720p", "1080p"]

    def test_720p_source_excludes_1080p_and_above(self):
        """720p source should include 720p, 480p, 360p only."""
        labels = self._labels(720)
        assert labels == ["360p", "480p", "720p"]
        assert "1080p" not in labels

    def test_480p_source(self):
        """480p source should include 480p and 360p only."""
        labels = self._labels(480)
        assert labels == ["360p", "480p"]
        assert "720p" not in labels


# ──────────────────────────────────────────────────────────────────────
# Metadata discovery filter tests (director / cast / keyword / exclude)
# ──────────────────────────────────────────────────────────────────────

MOVIE_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MOVIE_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MOVIE_C_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="function")
def metadata_movies(db_session: Session):
    """Seed with movies that have director, cast, and keywords."""
    movies = [
        movie_model.Movie(
            id=MOVIE_A_ID, title="FPV Forest Flight",
            release_date=date(2024, 1, 1),
            genres=["Documentary"], director="Pexels Creator",
            cast=["Drone Camera", "Forest Landscape"],
            keywords=["drone", "fpv", "forest", "aerial", "green forest"],
        ),
        movie_model.Movie(
            id=MOVIE_B_ID, title="Nature Walks",
            release_date=date(2023, 6, 15),
            genres=["Documentary"], director="Pexels Creator",
            cast=["Camera Operator", "Forest Landscape"],
            keywords=["nature", "forest", "walking"],
        ),
        movie_model.Movie(
            id=MOVIE_C_ID, title="City Lights",
            release_date=date(2022, 3, 10),
            genres=["Drama"], director="Urban Studios",
            cast=["Drone Camera"],
            keywords=["city", "night"],
        ),
    ]
    db_session.add_all(movies)
    db_session.commit()
    return movies


# ── Director filter ──────────────────────────────────────────────────

def test_director_exact_match(metadata_movies):
    """director=Pexels Creator → 2 movies."""
    r = client.get("/api/v1/movies?director=Pexels Creator")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert titles == {"FPV Forest Flight", "Nature Walks"}


def test_director_case_insensitive(metadata_movies):
    """director=pexels creator (lowercase) should still match."""
    r = client.get("/api/v1/movies?director=pexels creator")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_director_whitespace_normalized(metadata_movies):
    """director= Pexels   Creator  (extra spaces) should still match."""
    r = client.get("/api/v1/movies?director= Pexels   Creator ")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_director_no_match(metadata_movies):
    """director=Unknown Director → 0 results."""
    r = client.get("/api/v1/movies?director=Unknown Director")
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── Cast filter ──────────────────────────────────────────────────────

def test_cast_exact_match(metadata_movies):
    """cast=Drone Camera → FPV Forest Flight + City Lights."""
    r = client.get("/api/v1/movies?cast=Drone Camera")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert titles == {"FPV Forest Flight", "City Lights"}


def test_cast_case_insensitive(metadata_movies):
    """cast=drone camera (lowercase) → same 2 movies."""
    r = client.get("/api/v1/movies?cast=drone camera")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_cast_no_partial_match(metadata_movies):
    """cast=Camera must NOT match 'Drone Camera' or 'Camera Operator' — exact item only."""
    r = client.get("/api/v1/movies?cast=Camera")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_cast_exact_item_camera_operator(metadata_movies):
    """cast=Camera Operator → only Nature Walks."""
    r = client.get("/api/v1/movies?cast=Camera Operator")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert titles == {"Nature Walks"}


# ── Keyword filter ───────────────────────────────────────────────────

def test_keyword_exact_match(metadata_movies):
    """keyword=forest → FPV Forest Flight + Nature Walks."""
    r = client.get("/api/v1/movies?keyword=forest")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert titles == {"FPV Forest Flight", "Nature Walks"}


def test_keyword_with_hash_prefix(metadata_movies):
    """keyword=#forest should behave the same as keyword=forest."""
    r = client.get("/api/v1/movies?keyword=%23forest")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_keyword_case_insensitive(metadata_movies):
    """keyword=FOREST → same results."""
    r = client.get("/api/v1/movies?keyword=FOREST")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_keyword_no_cross_match(metadata_movies):
    """keyword=forest must NOT match 'green forest' unless exact 'forest' also exists."""
    # Both FPV and Nature have "forest" as an exact keyword → match.
    # City Lights does NOT have "forest" → no match.
    r = client.get("/api/v1/movies?keyword=forest")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert "City Lights" not in titles


def test_keyword_green_forest_exact(metadata_movies):
    """keyword=green forest → only FPV Forest Flight (has 'green forest' as an exact keyword)."""
    r = client.get("/api/v1/movies?keyword=green forest")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"] == "FPV Forest Flight"


# ── Exclude filter ───────────────────────────────────────────────────

def test_exclude_current_movie(metadata_movies):
    """exclude=<MOVIE_A_ID> with keyword=forest → only Nature Walks."""
    r = client.get(f"/api/v1/movies?keyword=forest&exclude={MOVIE_A_ID}")
    assert r.status_code == 200
    titles = {m["title"] for m in r.json()["items"]}
    assert "FPV Forest Flight" not in titles
    assert "Nature Walks" in titles


def test_exclude_invalid_uuid_ignored(metadata_movies):
    """exclude=not-a-uuid should be ignored, not cause an error."""
    r = client.get("/api/v1/movies?keyword=forest&exclude=not-a-uuid")
    assert r.status_code == 200
    assert r.json()["total"] == 2  # no exclusion applied


# ── Metadata endpoint remains public ─────────────────────────────────

def test_metadata_endpoint_public(metadata_movies):
    """Metadata filters work without authentication."""
    r = client.get("/api/v1/movies?director=Pexels Creator")
    assert r.status_code == 200
    assert r.json()["total"] == 2


# ── Existing filters still work ──────────────────────────────────────

def test_existing_search_with_metadata_movies(metadata_movies):
    """search=city → City Lights."""
    r = client.get("/api/v1/movies?search=city")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"] == "City Lights"


def test_existing_genre_with_metadata_movies(metadata_movies):
    """genre=Documentary → FPV + Nature."""
    r = client.get("/api/v1/movies?genre=Documentary")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_existing_year_with_metadata_movies(metadata_movies):
    """year=2022 → City Lights."""
    r = client.get("/api/v1/movies?year=2022")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"] == "City Lights"


def test_pagination_with_metadata_filter(metadata_movies):
    """Pagination works with metadata filters."""
    r = client.get("/api/v1/movies?director=Pexels Creator&limit=1&page=1")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
