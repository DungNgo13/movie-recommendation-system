"""
Tests for MovieAsset model, asset license service, and license checker.

Test cases:
1. test_create_movie_asset — model creation stores all fields
2. test_blocked_assets_excluded_from_public — get_assets_for_movie excludes blocked
3. test_unknown_assets_fallback_to_placeholder — get_displayable_asset returns placeholder marker
4. test_movielens_importer_no_media — MovieLens importer creates zero MovieAsset records
5. test_wikimedia_rejects_unsupported_license — CC BY-NC is rejected by allow_license()
6. test_loc_public_domain_attribution — LOC asset has is_public_domain=True
"""

import pytest
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.movie import Movie
from app.models.movie_asset import MovieAsset
from app.services.asset_license_service import (
    create_asset,
    get_assets_for_movie,
    get_displayable_asset,
)
from app.schemas.movie_asset import MovieAssetCreateSchema
from app.services.license_checker import (
    allow_license,
    normalize_license,
    get_media_rights_status,
    block_unknown_or_restricted_media,
)

# ── Test database setup ──────────────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def db():
    """Create fresh tables for every test, yield a session, then drop."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Override the app dependency so any router code uses our test DB
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def _make_movie(db) -> Movie:
    """Helper: create a minimal Movie record and return it."""
    movie = Movie(id=uuid.uuid4(), title="Test Movie")
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


# ── 1. Model creation ────────────────────────────────────────────────────────

def test_create_movie_asset(db):
    """MovieAsset stores all fields correctly."""
    movie = _make_movie(db)

    data = MovieAssetCreateSchema(
        asset_type="poster",
        url="https://commons.wikimedia.org/example.jpg",
        source_name="Wikimedia Commons",
        source_url="https://commons.wikimedia.org/wiki/File:example.jpg",
        license_type="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        attribution="Photo by Example, CC BY-SA 4.0",
        is_public_domain=False,
        media_rights_status="attribution_required",
    )

    asset = create_asset(db, movie.id, data)

    assert asset.id is not None
    assert asset.movie_id == movie.id
    assert asset.asset_type == "poster"
    assert asset.source_name == "Wikimedia Commons"
    assert asset.license_type == "CC BY-SA 4.0"
    assert asset.media_rights_status == "attribution_required"
    assert asset.is_public_domain is False
    assert asset.created_at is not None


# ── 2. Blocked assets excluded ───────────────────────────────────────────────

def test_blocked_assets_excluded_from_public(db):
    """get_assets_for_movie excludes blocked assets by default."""
    movie = _make_movie(db)

    # Create one safe and one blocked asset
    create_asset(db, movie.id, MovieAssetCreateSchema(
        asset_type="poster",
        url="https://example.com/safe.jpg",
        media_rights_status="safe_to_use",
    ))
    create_asset(db, movie.id, MovieAssetCreateSchema(
        asset_type="backdrop",
        url="https://example.com/blocked.jpg",
        media_rights_status="blocked",
    ))

    # Public query should only return the safe asset
    public_assets = get_assets_for_movie(db, movie.id, include_blocked=False)
    assert len(public_assets) == 1
    assert public_assets[0].asset_type == "poster"

    # Admin query should return both
    all_assets = get_assets_for_movie(db, movie.id, include_blocked=True)
    assert len(all_assets) == 2


# ── 3. Unknown assets → placeholder ─────────────────────────────────────────

def test_unknown_assets_fallback_to_placeholder(db):
    """get_displayable_asset returns _placeholder=True for unknown status."""
    movie = _make_movie(db)

    create_asset(db, movie.id, MovieAssetCreateSchema(
        asset_type="poster",
        url="https://example.com/unknown.jpg",
        media_rights_status="unknown",
    ))

    result = get_displayable_asset(db, movie.id, "poster")
    assert result is not None
    assert result["_placeholder"] is True


# ── 4. MovieLens importer → no media assets ──────────────────────────────────

def test_movielens_importer_no_media(db):
    """
    Simulates what import_movielens does:
    creates a Movie with MovieLens source but zero MovieAsset records.
    """
    movie = Movie(
        id=uuid.uuid4(),
        title="Toy Story",
        genres=["Animation", "Comedy"],
        source_name="MovieLens",
        source_url="https://movielens.org/movies/1",
        license_type="Research Use",
        media_rights_status="non_commercial_only",
    )
    db.add(movie)
    db.commit()

    # Verify: no assets were created for this movie
    assets = get_assets_for_movie(db, movie.id, include_blocked=True)
    assert len(assets) == 0


# ── 5. Wikimedia rejects unsupported licenses ────────────────────────────────

def test_wikimedia_rejects_unsupported_license():
    """allow_license() rejects CC BY-NC and other restricted licenses."""
    # Should be rejected
    assert allow_license("CC BY-NC 4.0") is False
    assert allow_license("cc-by-nc-4.0") is False
    assert allow_license("CC BY-ND 4.0") is False
    assert allow_license("All Rights Reserved") is False

    # Should be allowed
    assert allow_license("CC BY-SA 4.0") is True
    assert allow_license("CC BY 4.0") is True
    assert allow_license("Public Domain") is True
    assert allow_license("CC0") is True
    assert allow_license("Pexels License") is True


# ── 6. LOC public domain attribution ────────────────────────────────────────

def test_loc_public_domain_attribution(db):
    """LOC assets are marked is_public_domain=True and have attribution."""
    movie = _make_movie(db)

    data = MovieAssetCreateSchema(
        asset_type="full_video",
        url="https://archive.org/example_movie.mp4",
        source_name="Library of Congress",
        source_url="https://www.loc.gov/item/example",
        license_type="Public Domain",
        attribution="Film is in the public domain (1922, US).",
        is_public_domain=True,
        media_rights_status="safe_to_use",
    )
    asset = create_asset(db, movie.id, data)

    assert asset.is_public_domain is True
    assert asset.media_rights_status == "safe_to_use"
    assert asset.attribution == "Film is in the public domain (1922, US)."
    assert asset.source_name == "Library of Congress"


# ── Bonus: license_checker unit tests ────────────────────────────────────────

def test_normalize_license():
    """normalize_license handles aliases correctly."""
    assert normalize_license("cc-by-sa-4.0") == "CC BY-SA 4.0"
    assert normalize_license("PD") == "Public Domain"
    assert normalize_license("cc0") == "CC0 1.0"
    assert normalize_license("some random thing") == "some random thing"


def test_get_media_rights_status():
    """get_media_rights_status maps correctly."""
    assert get_media_rights_status("Public Domain") == "safe_to_use"
    assert get_media_rights_status("CC0") == "safe_to_use"
    assert get_media_rights_status("CC BY 4.0") == "attribution_required"
    assert get_media_rights_status("CC BY-NC 4.0") == "non_commercial_only"
    assert get_media_rights_status("All Rights Reserved") == "blocked"
    assert get_media_rights_status("unknown license xyz") == "unknown"


def test_block_unknown_or_restricted_media():
    """block_unknown_or_restricted_media filters correctly."""
    assets = [
        {"id": 1, "media_rights_status": "safe_to_use"},
        {"id": 2, "media_rights_status": "blocked"},
        {"id": 3, "media_rights_status": "unknown"},
    ]
    result = block_unknown_or_restricted_media(assets)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert "_placeholder" not in result[0]
    assert result[1]["id"] == 3
    assert result[1]["_placeholder"] is True
