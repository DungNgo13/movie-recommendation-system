import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..app.main import app
from ..app.database import Base, get_db

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_db.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the tables in the test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Apply the override for the get_db dependency
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_teardown():
    # Setup: create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown: drop tables
    Base.metadata.drop_all(bind=engine)


def test_create_movie():
    response = client.post(
        "/api/movies/",
        json={"title": "Test Movie", "description": "A great film", "release_year": 2023, "genre": "Action"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Movie"
    assert data["description"] == "A great film"
    assert "id" in data

def test_read_movie():
    # First, create a movie to read
    response = client.post(
        "/api/movies/",
        json={"title": "Another Movie", "description": "Another great film"},
    )
    assert response.status_code == 200
    movie_id = response.json()["id"]

    # Now, read it
    response = client.get(f"/api/movies/{movie_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Another Movie"
    assert data["id"] == movie_id

def test_read_inexistent_movie():
    response = client.get("/api/movies/9999")
    assert response.status_code == 404

def test_read_movies():
    # Clear and create a known state
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    client.post("/api/movies/", json={"title": "Movie 1"})
    client.post("/api/movies/", json={"title": "Movie 2"})

    response = client.get("/api/movies/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Movie 1"
    assert data[1]["title"] == "Movie 2"
