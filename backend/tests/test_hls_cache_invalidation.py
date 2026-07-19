"""
Tests for HLS cache invalidation behavior.

Verifies that the recommendation-engine TF-IDF cache is invalidated
at the correct moments during HLS processing:
  - After successful multi-quality conversion
  - After successful single-quality fallback
  - NOT after failed conversion
  - NOT after cancelled conversion
  - NOT during progress updates
"""
import os
from uuid import uuid4
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.movie import Movie
from app.database import Base


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=e)
    yield e
    e.dispose()


@pytest.fixture()
def db(engine):
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.rollback()
    session.close()


def _make_movie(db: Session) -> Movie:
    """Insert a movie with a source video path, ready for HLS processing."""
    m = Movie(
        id=uuid4(),
        title="Test HLS Movie",
        video_source_path="media/videos/source/test.mp4",
        processing_status="idle",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ---------------------------------------------------------------------------
# Helper: patch all external dependencies of process_hls_conversion
# ---------------------------------------------------------------------------

def _patch_hls_externals(db_session, movie, *,
                         multi_rc=0, fallback_rc=0,
                         master_exists=True, fallback_exists=True,
                         spawn_side_effect=None):
    """
    Return a dict of mock-patch context managers that isolate
    process_hls_conversion from the filesystem and FFmpeg.
    """
    patches = {}

    # Patch SessionLocal to return a mock session that wraps the real one
    # but whose close() is a no-op (so objects stay attached)
    mock_session = MagicMock(wraps=db_session)
    mock_session.close = MagicMock()  # no-op close
    patches["session"] = patch(
        "app.services.hls_service.SessionLocal", return_value=mock_session
    )

    # Patch os.path.exists to control playlist existence checks
    original_exists = os.path.exists

    def fake_exists(path):
        if "master.m3u8" in str(path):
            return master_exists
        if "playlist.m3u8" in str(path):
            return fallback_exists
        if str(path) == movie.video_source_path:
            return True
        return original_exists(path)

    patches["exists"] = patch("app.services.hls_service.os.path.exists", side_effect=fake_exists)

    # Patch os.makedirs, shutil.rmtree to avoid filesystem ops
    patches["makedirs"] = patch("app.services.hls_service.os.makedirs")
    patches["rmtree"] = patch("app.services.hls_service.shutil.rmtree")

    # Patch FFprobe-based helpers
    patches["duration"] = patch(
        "app.services.hls_service.get_video_duration", return_value=120.0
    )
    patches["dimensions"] = patch(
        "app.services.hls_service.get_video_dimensions", return_value=(1920, 1080)
    )
    patches["audio"] = patch(
        "app.services.hls_service.has_audio_stream", return_value=True
    )

    # Patch _spawn_ffmpeg to avoid running real FFmpeg
    if spawn_side_effect is not None:
        patches["spawn"] = patch(
            "app.services.hls_service._spawn_ffmpeg", side_effect=spawn_side_effect
        )
    else:
        call_count = {"n": 0}

        def fake_spawn(cmd, db_arg, db_movie, total_duration, movie_id=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return (multi_rc, [])
            return (fallback_rc, [])

        patches["spawn"] = patch(
            "app.services.hls_service._spawn_ffmpeg", side_effect=fake_spawn
        )

    # Patch _build_multi_quality_cmd and _build_single_quality_cmd
    patches["multi_cmd"] = patch(
        "app.services.hls_service._build_multi_quality_cmd",
        return_value=(["ffmpeg", "-fake"], ["720p", "360p"]),
    )
    patches["single_cmd"] = patch(
        "app.services.hls_service._build_single_quality_cmd",
        return_value=(["ffmpeg", "-fake-fallback"], "playlist.m3u8"),
    )

    # The key mock: _invalidate_rec_cache
    patches["invalidate"] = patch(
        "app.services.hls_service._invalidate_rec_cache"
    )

    return patches


def _enter_patches(patches):
    """Enter all patch context managers and return the invalidate mock."""
    mocks = {}
    for key, p in patches.items():
        mocks[key] = p.start()
    return mocks


def _exit_patches(patches):
    """Stop all patches."""
    for p in patches.values():
        p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHlsCacheInvalidation:
    """Verify recommendation cache invalidation after HLS processing."""

    def test_multi_quality_success_invalidates_cache(self, db):
        """Successful multi-quality HLS conversion calls _invalidate_rec_cache once."""
        movie = _make_movie(db)
        patches = _patch_hls_externals(db, movie, multi_rc=0, master_exists=True)
        mocks = _enter_patches(patches)
        try:
            from app.services.hls_service import process_hls_conversion
            process_hls_conversion(movie.id)
            assert mocks["invalidate"].call_count == 1
        finally:
            _exit_patches(patches)

        # Verify status via direct query (session is still open)
        result = db.query(Movie).filter(Movie.id == movie.id).first()
        assert result.processing_status == "ready"

    def test_fallback_success_invalidates_cache(self, db):
        """Successful fallback (480p) conversion calls _invalidate_rec_cache once."""
        movie = _make_movie(db)
        patches = _patch_hls_externals(
            db, movie,
            multi_rc=1, master_exists=False,
            fallback_rc=0, fallback_exists=True,
        )
        mocks = _enter_patches(patches)
        try:
            from app.services.hls_service import process_hls_conversion
            process_hls_conversion(movie.id)
            assert mocks["invalidate"].call_count == 1
        finally:
            _exit_patches(patches)

        result = db.query(Movie).filter(Movie.id == movie.id).first()
        assert result.processing_status == "ready"

    def test_failed_conversion_does_not_invalidate_cache(self, db):
        """Failed conversion (both attempts fail) does NOT call _invalidate_rec_cache."""
        movie = _make_movie(db)
        patches = _patch_hls_externals(
            db, movie,
            multi_rc=1, master_exists=False,
            fallback_rc=1, fallback_exists=False,
        )
        mocks = _enter_patches(patches)
        try:
            from app.services.hls_service import process_hls_conversion
            process_hls_conversion(movie.id)
            assert mocks["invalidate"].call_count == 0
        finally:
            _exit_patches(patches)

        result = db.query(Movie).filter(Movie.id == movie.id).first()
        assert result.processing_status == "failed"

    def test_cancelled_conversion_does_not_invalidate_cache(self, db):
        """Cancelled conversion does NOT call _invalidate_rec_cache as a ready transition."""
        movie = _make_movie(db)

        def cancel_during_spawn(cmd, db_arg, db_movie, total_duration, movie_id=None):
            # Simulate the admin cancelling mid-encode by changing status
            db_movie.processing_status = "cancelled"
            db_arg.commit()
            return (0, [])

        patches = _patch_hls_externals(
            db, movie, multi_rc=0, master_exists=True,
            spawn_side_effect=cancel_during_spawn,
        )
        mocks = _enter_patches(patches)
        try:
            from app.services.hls_service import process_hls_conversion
            process_hls_conversion(movie.id)
            # The guard `if db_movie.processing_status != "processing"` prevents
            # the ready transition, so cache should NOT be invalidated
            assert mocks["invalidate"].call_count == 0
        finally:
            _exit_patches(patches)

    def test_progress_updates_do_not_repeatedly_invalidate_cache(self, db):
        """Progress updates during encoding do NOT trigger extra cache invalidation."""
        movie = _make_movie(db)
        progress_updates = []

        def spy_spawn(cmd, db_arg, db_movie, total_duration, movie_id=None):
            # Simulate multiple progress updates (like _spawn_ffmpeg does)
            for pct in [10, 25, 50, 75, 90]:
                db_movie.processing_progress = pct
                db_arg.commit()
                progress_updates.append(pct)
            return (0, [])

        patches = _patch_hls_externals(
            db, movie, multi_rc=0, master_exists=True,
            spawn_side_effect=spy_spawn,
        )
        mocks = _enter_patches(patches)
        try:
            from app.services.hls_service import process_hls_conversion
            process_hls_conversion(movie.id)
            # Progress was updated 5 times, but cache invalidation should happen
            # only once — at the final ready transition, not during progress
            assert len(progress_updates) == 5
            assert mocks["invalidate"].call_count == 1
        finally:
            _exit_patches(patches)
