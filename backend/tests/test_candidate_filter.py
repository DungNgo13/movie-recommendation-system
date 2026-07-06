"""
Tests for the RECOMMEND_ONLY_UPLOADED_MOVIES candidate pool filter.

Verifies that the recommendation engine correctly includes/excludes movies
based on their video upload status when the config flag is toggled.
"""

import os
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.movie import Movie
from app.models.user import User
from app.models.rating import Rating
from app.services.recommendation.vectorizer import (
    _candidate_query,
    _should_filter_uploaded_only,
    fit_vectorizer,
    get_movie_vectors,
    invalidate_cache,
)
from app.services.recommendation.engine import get_recommendations

# ─── Test fixtures ────────────────────────────────────────────────────────────

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _setup_db():
    """Create tables before each test, drop after."""
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


def _make_movie(
    db,
    title: str,
    genres: list[str] | None = None,
    video_source_path: str | None = None,
    hls_playlist_path: str | None = None,
    processing_status: str = "no_video",
) -> Movie:
    """Helper to insert a movie with controlled video fields."""
    movie = Movie(
        id=uuid.uuid4(),
        title=title,
        overview=f"Overview for {title}",
        release_date=date(2024, 1, 1),
        genres=genres or ["Drama"],
        cast=["Actor A"],
        keywords=["tag"],
        director="Director X",
        video_source_path=video_source_path,
        hls_playlist_path=hls_playlist_path,
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


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestCandidatePoolFilter:
    """Test the RECOMMEND_ONLY_UPLOADED_MOVIES config flag."""

    def test_movie_without_video_excluded_when_flag_true(self, db):
        """
        When RECOMMEND_ONLY_UPLOADED_MOVIES=true, a movie with no video
        should NOT be in the candidate pool.
        """
        # Movie with no video at all
        no_video = _make_movie(db, "No Video Movie")
        # Movie with uploaded video
        has_video = _make_movie(
            db, "Has Video Movie",
            video_source_path="/media/videos/source/test.mp4",
            processing_status="uploaded",
        )

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "true"}):
            invalidate_cache()
            candidates = _candidate_query(db).all()
            candidate_ids = {str(m.id) for m in candidates}

            assert str(has_video.id) in candidate_ids
            assert str(no_video.id) not in candidate_ids

    def test_movie_with_hls_ready_included(self, db):
        """
        A movie with processing_status='ready' should be included in the
        candidate pool even when the filter is active.
        """
        ready_movie = _make_movie(
            db, "Ready Movie",
            hls_playlist_path="/media/videos/hls/test/master.m3u8",
            processing_status="ready",
        )

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "true"}):
            invalidate_cache()
            candidates = _candidate_query(db).all()
            candidate_ids = {str(m.id) for m in candidates}

            assert str(ready_movie.id) in candidate_ids

    def test_movie_without_video_included_when_flag_false(self, db):
        """
        When RECOMMEND_ONLY_UPLOADED_MOVIES=false, ALL movies should be
        in the candidate pool regardless of video status.
        """
        no_video = _make_movie(db, "No Video Movie 2")
        has_video = _make_movie(
            db, "Has Video Movie 2",
            video_source_path="/media/videos/source/test2.mp4",
            processing_status="uploaded",
        )

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "false"}):
            invalidate_cache()
            candidates = _candidate_query(db).all()
            candidate_ids = {str(m.id) for m in candidates}

            assert str(has_video.id) in candidate_ids
            assert str(no_video.id) in candidate_ids

    def test_vectorizer_only_indexes_uploaded_movies(self, db):
        """
        When the flag is true, fit_vectorizer should only index movies
        with uploaded video in the TF-IDF matrix.
        """
        _make_movie(db, "No Video Sci-Fi", genres=["Sci-Fi"])
        uploaded = _make_movie(
            db, "Uploaded Drama",
            genres=["Drama"],
            video_source_path="/media/videos/source/drama.mp4",
            processing_status="uploaded",
        )

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "true"}):
            invalidate_cache()
            matrix, movie_ids = get_movie_vectors(db)

            assert matrix is not None
            assert len(movie_ids) == 1
            assert movie_ids[0] == str(uploaded.id)

    def test_recommendations_exclude_no_video_movies(self, db):
        """
        End-to-end: recommendations should not include movies without
        uploaded video when the filter flag is active.
        """
        user = _make_user(db)

        # Create 2 movies with video (user will rate one)
        movie_a = _make_movie(
            db, "Action Film A",
            genres=["Action", "Thriller"],
            video_source_path="/media/videos/source/a.mp4",
            processing_status="uploaded",
        )
        movie_b = _make_movie(
            db, "Action Film B",
            genres=["Action", "Adventure"],
            video_source_path="/media/videos/source/b.mp4",
            processing_status="uploaded",
        )

        # Create 1 movie WITHOUT video (should be excluded from recs)
        movie_no_vid = _make_movie(
            db, "Action Film No Video",
            genres=["Action", "Thriller"],
        )

        # User rates movie_a → profile favors Action
        _rate_movie(db, user, movie_a, 5)

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "true"}):
            invalidate_cache()
            recs = get_recommendations(db, user.id, top_n=10)
            rec_ids = {r["id"] for r in recs}

            # movie_b should be recommended (similar genre, has video)
            # movie_no_vid should NOT appear (no video)
            assert str(movie_no_vid.id) not in rec_ids

    def test_cold_start_respects_filter(self, db):
        """
        Cold-start fallback should only return movies from the candidate
        pool when the filter is active.
        """
        user = _make_user(db)

        _make_movie(db, "Cold Start No Video")
        has_vid = _make_movie(
            db, "Cold Start Has Video",
            video_source_path="/media/videos/source/cs.mp4",
            processing_status="uploaded",
        )

        with patch.dict(os.environ, {"RECOMMEND_ONLY_UPLOADED_MOVIES": "true"}):
            invalidate_cache()
            # User has no interactions → cold start
            recs = get_recommendations(db, user.id, top_n=10)
            rec_ids = {r["id"] for r in recs}

            assert str(has_vid.id) in rec_ids
            # The no-video movie should be excluded
            assert len(recs) == 1

    def test_default_flag_is_true(self):
        """
        The default value of RECOMMEND_ONLY_UPLOADED_MOVIES should be true
        when the env variable is not set.
        """
        env = os.environ.copy()
        env.pop("RECOMMEND_ONLY_UPLOADED_MOVIES", None)
        with patch.dict(os.environ, env, clear=True):
            assert _should_filter_uploaded_only() is True
