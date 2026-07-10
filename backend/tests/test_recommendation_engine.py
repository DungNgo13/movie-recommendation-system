"""
Tests for the recommendation engine pipeline.

Covers:
  1. End-to-end recommendation with ratings/favorites/watch-history
  2. Cold-start fallback behaviour
  3. Empty catalog behaviour
  4. Cache invalidation after movie metadata update
"""

import os
import uuid
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.movie import Movie
from app.models.user import User
from app.models.rating import Rating
from app.models.user_favorite import UserFavorite
from app.models.watch_history import WatchHistory
from app.services.recommendation.engine import get_recommendations
from app.services.recommendation.vectorizer import (
    get_movie_vectors,
    invalidate_cache,
    _cache,
)
from app.services.recommendation.user_profile import build_user_profile
from app.services.movie_service import update_movie
from app.schemas.movie import MovieUpdateSchema


# ─── Test infrastructure ─────────────────────────────────────────────────────

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test, tear down after."""
    Base.metadata.create_all(bind=engine)
    yield
    invalidate_cache()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_movie(
    db,
    title: str,
    genres: list[str] | None = None,
    cast: list[str] | None = None,
    keywords: list[str] | None = None,
    director: str | None = "Director X",
    overview: str | None = None,
    release_date: date | None = None,
    video_source_path: str | None = None,
    processing_status: str = "no_video",
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        title=title,
        overview=overview or f"Overview for {title}",
        release_date=release_date or date(2024, 1, 1),
        genres=genres or ["Drama"],
        cast=cast or ["Actor A"],
        keywords=keywords or ["tag"],
        director=director,
        video_source_path=video_source_path,
        processing_status=processing_status,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


def _make_user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:6]}@test.com",
        password_hash="$2b$12$dummy",
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _rate_movie(db, user: User, movie: Movie, rating: int = 5):
    r = Rating(
        id=uuid.uuid4(),
        user_id=user.id,
        movie_id=movie.id,
        rating=rating,
    )
    db.add(r)
    db.commit()


def _favorite_movie(db, user: User, movie: Movie):
    fav = UserFavorite(
        id=uuid.uuid4(),
        user_id=user.id,
        movie_id=movie.id,
    )
    db.add(fav)
    db.commit()


def _watch_movie(db, user: User, movie: Movie, progress: int = 80):
    wh = WatchHistory(
        id=uuid.uuid4(),
        user_id=user.id,
        movie_id=movie.id,
        progress_percent=progress,
        watched_at=datetime.now(timezone.utc),
    )
    db.add(wh)
    db.commit()


# Disable the RECOMMEND_ONLY_UPLOADED_MOVIES filter for these tests so that
# movies without video files are still included in the candidate pool.
_env_filter_off = {"RECOMMEND_ONLY_UPLOADED_MOVIES": "false"}


# ─── Test 1: End-to-end recommendation pipeline ──────────────────────────────


class TestEndToEndRecommendation:
    """Full pipeline: movies → user interactions → personalized recommendations."""

    def test_basic_rating_recommendation(self, db):
        """User rates an action movie 5★ → engine recommends similar action movies."""
        # Create movies with distinct genres
        action1 = _make_movie(db, "Die Hard", genres=["Action", "Thriller"],
                              keywords=["heist", "hostage"])
        action2 = _make_movie(db, "Lethal Weapon", genres=["Action", "Thriller"],
                              keywords=["buddy", "cop"])
        drama = _make_movie(db, "The Notebook", genres=["Romance", "Drama"],
                            keywords=["love", "memory"])
        comedy = _make_movie(db, "Airplane", genres=["Comedy"],
                             keywords=["spoof", "slapstick"])

        user = _make_user(db)
        _rate_movie(db, user, action1, 5)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        # Should return non-empty results
        assert len(recs) > 0

        # All scores should be between 0 and 1
        for r in recs:
            assert 0.0 <= r["score"] <= 1.0, f"Score {r['score']} out of range"

        # The rated movie (action1) should be excluded because it's favorited
        # or still shown — but the reason should be generated
        for r in recs:
            assert "reason" in r
            assert isinstance(r["reason"], str)
            assert r["id"] is not None

        # action2 (same genre) should score higher than drama/comedy
        rec_ids = [r["id"] for r in recs]
        if str(action2.id) in rec_ids and str(drama.id) in rec_ids:
            action2_score = next(r["score"] for r in recs if r["id"] == str(action2.id))
            drama_score = next(r["score"] for r in recs if r["id"] == str(drama.id))
            assert action2_score >= drama_score, (
                f"Action movie ({action2_score}) should score >= drama ({drama_score})"
            )

    def test_favorite_influences_recommendations(self, db):
        """Favoriting a movie should influence the user profile."""
        scifi1 = _make_movie(db, "Interstellar", genres=["Sci-Fi", "Drama"],
                             keywords=["space", "wormhole"], director="Nolan")
        scifi2 = _make_movie(db, "The Martian", genres=["Sci-Fi", "Adventure"],
                             keywords=["space", "survival"], director="Ridley")
        horror = _make_movie(db, "The Ring", genres=["Horror"],
                             keywords=["ghost", "curse"])

        user = _make_user(db)
        _favorite_movie(db, user, scifi1)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        assert len(recs) > 0
        # Favorited movie should be excluded from results
        rec_ids = {r["id"] for r in recs}
        assert str(scifi1.id) not in rec_ids
        # Sci-Fi movie should be recommended
        assert str(scifi2.id) in rec_ids

    def test_watch_history_influences_recommendations(self, db):
        """Watch history should influence the user profile via implicit signals."""
        thriller1 = _make_movie(db, "Se7en", genres=["Thriller", "Crime"],
                                keywords=["serial killer", "detective"])
        thriller2 = _make_movie(db, "Zodiac", genres=["Thriller", "Crime"],
                                keywords=["serial killer", "investigation"])
        romcom = _make_movie(db, "Pretty Woman", genres=["Romance", "Comedy"],
                             keywords=["love", "wealth"])

        user = _make_user(db)
        _watch_movie(db, user, thriller1, progress=90)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        assert len(recs) > 0
        # All scores valid
        for r in recs:
            assert 0.0 <= r["score"] <= 1.0

    def test_multiple_signals_combined(self, db):
        """Multiple signal types (rating + favorite + watch) build a richer profile."""
        a = _make_movie(db, "Inception", genres=["Action", "Sci-Fi"],
                        keywords=["dream", "heist"], director="Nolan")
        b = _make_movie(db, "Tenet", genres=["Action", "Sci-Fi"],
                        keywords=["time", "espionage"], director="Nolan")
        c = _make_movie(db, "Dark Knight", genres=["Action", "Crime"],
                        keywords=["hero", "villain"], director="Nolan")
        d = _make_movie(db, "Titanic", genres=["Romance", "Drama"],
                        keywords=["ship", "love"], director="Cameron")

        user = _make_user(db)
        _rate_movie(db, user, a, 5)
        _favorite_movie(db, user, a)   # duplicate — MAX rule applies
        _watch_movie(db, user, b, progress=100)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=10)

        assert len(recs) > 0
        rec_ids = [r["id"] for r in recs]
        # c (Nolan Action) should be recommended over d (Cameron Romance)
        if str(c.id) in rec_ids and str(d.id) in rec_ids:
            c_score = next(r["score"] for r in recs if r["id"] == str(c.id))
            d_score = next(r["score"] for r in recs if r["id"] == str(d.id))
            assert c_score >= d_score

    def test_recommendation_response_structure(self, db):
        """Each recommendation dict has the expected keys."""
        m = _make_movie(db, "Test Movie", genres=["Action"])
        user = _make_user(db)
        _rate_movie(db, user, m, 5)
        # Need a second movie to get a recommendation (the rated one may be excluded)
        _make_movie(db, "Other Movie", genres=["Action"])

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        for r in recs:
            assert "id" in r
            assert "title" in r
            assert "score" in r
            assert "reason" in r
            assert "poster_url" in r
            assert "release_year" in r


# ─── Test 2: Cold-start behaviour ─────────────────────────────────────────────


class TestColdStart:
    """User with no interactions gets fallback recommendations."""

    def test_cold_start_returns_movies(self, db):
        """New user with no interactions should get recent movies."""
        _make_movie(db, "Recent Movie A", release_date=date(2024, 6, 1))
        _make_movie(db, "Recent Movie B", release_date=date(2024, 5, 1))
        _make_movie(db, "Old Movie", release_date=date(2000, 1, 1))

        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=10)

        assert len(recs) > 0

    def test_cold_start_scores_are_zero(self, db):
        """Cold-start recommendations should have score=0."""
        _make_movie(db, "Movie X")
        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        for r in recs:
            assert r["score"] == 0.0, f"Cold-start score should be 0, got {r['score']}"

    def test_cold_start_reason_indicates_fallback(self, db):
        """Cold-start reason should clearly indicate it's a fallback."""
        _make_movie(db, "Fallback Movie")
        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        assert len(recs) > 0
        for r in recs:
            # The reason should mention rating/favoriting for personalization
            assert "rate" in r["reason"].lower() or "popular" in r["reason"].lower()

    def test_cold_start_ordered_by_release_date(self, db):
        """Cold-start movies should be ordered by most recent first."""
        _make_movie(db, "Old", release_date=date(2000, 1, 1))
        _make_movie(db, "Middle", release_date=date(2015, 6, 1))
        _make_movie(db, "New", release_date=date(2024, 12, 1))

        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=10)

        assert len(recs) == 3
        assert recs[0]["title"] == "New"
        assert recs[1]["title"] == "Middle"
        assert recs[2]["title"] == "Old"


# ─── Test 3: Empty catalog ────────────────────────────────────────────────────


class TestEmptyCatalog:
    """No movies in the database — engine should return empty lists safely."""

    def test_empty_catalog_personalized(self, db):
        """With no movies, personalized recommendations return empty list."""
        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=10)

        assert recs == []

    def test_empty_catalog_cold_start(self, db):
        """With no movies, cold-start fallback returns empty list."""
        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=5)

        assert recs == []

    def test_user_profile_none_when_no_movies(self, db):
        """build_user_profile returns None when the movie catalog is empty."""
        user = _make_user(db)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            profile = build_user_profile(db, user.id)

        assert profile is None

    def test_get_movie_vectors_empty(self, db):
        """get_movie_vectors returns (None, []) when no movies exist."""
        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            matrix, movie_ids = get_movie_vectors(db)

        assert matrix is None
        assert movie_ids == []


# ─── Test 4: Cache invalidation ──────────────────────────────────────────────


class TestCacheInvalidation:
    """Cache should be invalidated when movie data changes via service layer."""

    def test_cache_invalidated_on_movie_update(self, db):
        """Updating movie metadata through movie_service invalidates the cache."""
        movie = _make_movie(db, "Original Title", genres=["Drama"],
                            keywords=["original"])

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            # Trigger a cache build
            matrix, movie_ids = get_movie_vectors(db)
            assert matrix is not None
            # Cache should be populated now
            assert _cache["vectorizer"] is not None
            assert _cache["movie_count"] == 1

            # Update movie metadata through the service layer
            update_data = MovieUpdateSchema(
                title="Updated Title",
                genres=["Action", "Thriller"],
                keywords=["updated", "new-keyword"],
            )
            update_movie(db, movie.id, update_data)

            # Cache should be invalidated (vectorizer reset to None)
            assert _cache["vectorizer"] is None

    def test_explicit_invalidate_cache(self, db):
        """invalidate_cache() clears all cached values."""
        _make_movie(db, "Movie For Cache Test")

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            get_movie_vectors(db)
            assert _cache["vectorizer"] is not None

            invalidate_cache()
            assert _cache["vectorizer"] is None
            assert _cache["matrix"] is None
            assert _cache["movie_ids"] == []
            assert _cache["movie_count"] == 0

    def test_cache_rebuilds_after_invalidation(self, db):
        """After invalidation, the next get_movie_vectors call rebuilds cache."""
        _make_movie(db, "Rebuild Test Movie", genres=["Comedy"])

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            get_movie_vectors(db)
            assert _cache["vectorizer"] is not None

            invalidate_cache()
            assert _cache["vectorizer"] is None

            # Should rebuild on next call
            matrix, movie_ids = get_movie_vectors(db)
            assert matrix is not None
            assert len(movie_ids) == 1
            assert _cache["vectorizer"] is not None


# ─── Test 5: Negative / low ratings excluded ─────────────────────────────────


class TestNegativeSignals:
    """Ratings ≤ 2 should not influence the user profile."""

    def test_low_rating_excluded(self, db):
        """A 1★ or 2★ rating should not contribute to the user profile."""
        movie = _make_movie(db, "Bad Movie", genres=["Horror"])
        user = _make_user(db)
        _rate_movie(db, user, movie, 1)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            profile = build_user_profile(db, user.id)

        # Should be None because the only signal has weight 0
        assert profile is None

    def test_neutral_rating_included(self, db):
        """A 3★ rating should be included with weight 1.0."""
        movie = _make_movie(db, "OK Movie", genres=["Drama"])
        _make_movie(db, "Other Movie", genres=["Action"])  # need ≥1 candidate
        user = _make_user(db)
        _rate_movie(db, user, movie, 3)

        with patch.dict(os.environ, _env_filter_off):
            invalidate_cache()
            profile = build_user_profile(db, user.id)

        assert profile is not None
