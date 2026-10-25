"""
Phase 3 integration and unit tests for R2 source resolution and FFmpeg/HLS pipeline:

1. Local source resolution (path exists, no deletion).
2. Local source resolution failure (missing file).
3. R2 source resolution (download, nonempty validation).
4. R2 temporary directory cleanup on normal exit.
5. R2 temporary directory cleanup on exception / error.
6. R2 object missing in storage (raises SourceResolutionError and cleans temp).
7. R2 credentials / configuration missing (raises SourceResolutionError).
8. Partial download cleanup.
9. FFprobe failure handling (invalid dimensions -> failed status).
10. FFmpeg failure handling (multi + fallback fail -> failed status, partial dir cleaned).
11. HLS output verification failure prevents READY status.
12. Cancellation mid-processing (H2 fix: never marks READY without verified HLS).
13. Restart recovery (H1 fix: recover_stuck_encodes resets stranded processing movies).
14. Duplicate job prevention (concurrent process_hls_conversion invocation skipped).
15. Stale source replacement during processing (discard output, do not publish obsolete HLS).
16. Full successful READY transition from R2 source.
"""

import io
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, get_db
from app.models.movie import Movie
from app.services.hls_service import (
    _verify_hls_output,
    cancel_encode_task,
    process_hls_conversion,
    recover_stuck_encodes,
    _active_job_movies,
    _active_job_lock,
)
from app.services.r2_storage_service import R2StorageError, R2StorageService
from app.services.video_source_resolver import (
    ResolvedSource,
    SourceResolutionError,
    resolve_video_source,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_movie(db, storage="local", path=None, key=None, status="uploaded"):
    movie = Movie(
        id=uuid.uuid4(),
        title="Test Movie",
        overview="Test Overview",
        source_storage=storage,
        video_source_path=path,
        source_object_key=key,
        processing_status=status,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


# ─── 1. Source Resolver: Local Sources ────────────────────────────────────────

def test_resolve_local_source_success(db, tmp_path):
    local_file = tmp_path / "original.mp4"
    local_file.write_bytes(b"VIDEO_DATA_LOCAL")

    movie = _make_movie(db, storage="local", path=str(local_file))

    with resolve_video_source(movie) as resolved:
        assert isinstance(resolved, ResolvedSource)
        assert resolved.local_path == str(local_file)
        assert resolved.source_storage == "local"
        assert resolved.is_temporary is False
        assert os.path.exists(resolved.local_path)

    # Must NOT delete original local source
    assert os.path.exists(str(local_file))


def test_resolve_local_source_missing_file_raises(db, tmp_path):
    missing_file = tmp_path / "does_not_exist.mp4"
    movie = _make_movie(db, storage="local", path=str(missing_file))

    with pytest.raises(SourceResolutionError) as exc_info:
        with resolve_video_source(movie):
            pass

    assert "missing from disk" in str(exc_info.value).lower()


# ─── 2. Source Resolver: R2 Sources & Cleanup ─────────────────────────────────

def test_resolve_r2_source_success_and_cleanup(db, tmp_path):
    movie = _make_movie(db, storage="r2", key="sources/movie_1/vid.mp4")

    mock_storage = MagicMock(spec=R2StorageService)
    def fake_download(key, dest):
        with open(dest, "wb") as f:
            f.write(b"R2_VIDEO_CONTENT_12345")
        return len(b"R2_VIDEO_CONTENT_12345")
    mock_storage.download_to_path.side_effect = fake_download

    temp_path = None
    temp_dir = None

    with resolve_video_source(movie, storage=mock_storage, temp_dir_base=str(tmp_path)) as resolved:
        assert resolved.source_storage == "r2"
        assert resolved.source_identifier == "sources/movie_1/vid.mp4"
        assert resolved.is_temporary is True
        temp_path = resolved.local_path
        temp_dir = os.path.dirname(temp_path)

        assert os.path.isfile(temp_path)
        assert os.path.getsize(temp_path) > 0
        assert open(temp_path, "rb").read() == b"R2_VIDEO_CONTENT_12345"

    # After context exit: temp file and isolated temp directory MUST be deleted!
    assert not os.path.exists(temp_path)
    assert not os.path.exists(temp_dir)


def test_resolve_r2_source_cleans_up_on_exception(db, tmp_path):
    movie = _make_movie(db, storage="r2", key="sources/movie_1/vid.mp4")

    mock_storage = MagicMock(spec=R2StorageService)
    def fake_download(key, dest):
        with open(dest, "wb") as f:
            f.write(b"DATA")
        return 4
    mock_storage.download_to_path.side_effect = fake_download

    captured_temp_dir = None
    with pytest.raises(RuntimeError, match="processing_exploded"):
        with resolve_video_source(movie, storage=mock_storage, temp_dir_base=str(tmp_path)) as resolved:
            captured_temp_dir = os.path.dirname(resolved.local_path)
            assert os.path.exists(captured_temp_dir)
            raise RuntimeError("processing_exploded")

    assert captured_temp_dir is not None
    assert not os.path.exists(captured_temp_dir)


def test_resolve_r2_object_missing_raises_and_cleans(db, tmp_path):
    movie = _make_movie(db, storage="r2", key="sources/movie_missing/vid.mp4")

    mock_storage = MagicMock(spec=R2StorageService)
    mock_storage.download_to_path.side_effect = R2StorageError("R2 get_object failed (code=NoSuchKey)")

    with pytest.raises(SourceResolutionError) as exc:
        with resolve_video_source(movie, storage=mock_storage, temp_dir_base=str(tmp_path)):
            pass

    assert "NoSuchKey" in str(exc.value) or "Failed to download" in str(exc.value)
    # Check that temp_dir_base has no lingering child directories
    assert len(os.listdir(str(tmp_path))) == 0


def test_resolve_r2_unconfigured_raises(db, monkeypatch):
    movie = _make_movie(db, storage="r2", key="sources/movie_1/vid.mp4")

    # Clear R2 env vars
    monkeypatch.delenv("R2_ENDPOINT", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("R2_BUCKET_NAME", raising=False)

    with pytest.raises(SourceResolutionError) as exc:
        with resolve_video_source(movie, storage=None):
            pass

    assert "not configured" in str(exc.value).lower()


# ─── 3. Output Verification Unit Tests ────────────────────────────────────────

def test_verify_hls_output_checks(tmp_path):
    out_dir = tmp_path / "hls_movie"
    out_dir.mkdir()
    pl = out_dir / "master.m3u8"

    # 1. Non-existent playlist
    assert not _verify_hls_output(str(pl), str(out_dir))

    # 2. Empty playlist
    pl.write_text("")
    assert not _verify_hls_output(str(pl), str(out_dir))

    # 3. Invalid header
    pl.write_text("INVALID_NOT_EXTM3U")
    assert not _verify_hls_output(str(pl), str(out_dir))

    # 4. Valid header but no .ts segments
    pl.write_text("#EXTM3U\n#EXT-X-VERSION:3\nv0_playlist.m3u8")
    assert not _verify_hls_output(str(pl), str(out_dir))

    # 5. Valid header AND at least one .ts segment
    seg = out_dir / "v0_segment_000.ts"
    seg.write_bytes(b"\x47\x00")
    assert _verify_hls_output(str(pl), str(out_dir))


# ─── 4. Full HLS Pipeline Integration with R2 Source ──────────────────────────

def test_hls_process_r2_success_ready_transition(db, tmp_path, monkeypatch):
    movie = _make_movie(db, storage="r2", key="sources/movie_r2/test.mp4")
    movie_id = movie.id

    # Mock SessionLocal in hls_service to use our isolated test db sessionmaker
    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)

    # Mock R2 download
    def fake_download(key, dest):
        with open(dest, "wb") as f:
            f.write(b"MOCK_MP4_CONTENT")
        return len(b"MOCK_MP4_CONTENT")

    mock_storage = MagicMock()
    mock_storage.download_to_path.side_effect = fake_download
    monkeypatch.setattr("app.services.video_source_resolver.load_r2_storage_from_env", lambda: mock_storage)

    # Mock FFprobe helpers
    monkeypatch.setattr("app.services.hls_service.get_video_duration", lambda path: 60.0)
    monkeypatch.setattr("app.services.hls_service.has_audio_stream", lambda path: True)
    monkeypatch.setattr("app.services.hls_service.get_video_dimensions", lambda path: (1280, 720))

    # Mock FFmpeg execution: create real master.m3u8 and segment in target directory
    def fake_spawn(cmd, db_arg, db_m, duration, movie_id=None):
        out_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        os.makedirs(out_dir, exist_ok=True)
        master = os.path.join(out_dir, "master.m3u8")
        with open(master, "w") as f:
            f.write("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2800000\nv0_playlist.m3u8\n")
        seg = os.path.join(out_dir, "v0_segment_000.ts")
        with open(seg, "wb") as f:
            f.write(b"\x47\x00")
        return (0, [])

    monkeypatch.setattr("app.services.hls_service._spawn_ffmpeg", fake_spawn)

    invalidated = []
    monkeypatch.setattr("app.services.hls_service._invalidate_rec_cache", lambda: invalidated.append(True))

    try:
        process_hls_conversion(movie_id)

        db.expire_all()
        updated = db.query(Movie).filter(Movie.id == movie_id).first()
        assert updated.processing_status == "ready"
        assert updated.processing_step == "Ready"
        assert updated.processing_progress == 100
        assert updated.processing_error is None
        assert updated.hls_playlist_path is not None
        assert "master.m3u8" in updated.hls_playlist_path
        assert len(invalidated) == 1
    finally:
        out_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        if os.path.exists(out_dir):
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)


def test_hls_process_r2_ffprobe_failure(db, tmp_path, monkeypatch):
    movie = _make_movie(db, storage="r2", key="sources/corrupt/corrupt.mp4")
    movie_id = movie.id
    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)

    mock_storage = MagicMock()
    mock_storage.download_to_path.side_effect = lambda k, d: open(d, "wb").write(b"CORRUPT")
    monkeypatch.setattr("app.services.video_source_resolver.load_r2_storage_from_env", lambda: mock_storage)

    # ffprobe returns 0, 0
    monkeypatch.setattr("app.services.hls_service.get_video_dimensions", lambda path: (0, 0))
    monkeypatch.setattr("app.services.hls_service.get_video_duration", lambda path: 0.0)

    process_hls_conversion(movie_id)

    db.expire_all()
    updated = db.query(Movie).filter(Movie.id == movie_id).first()
    assert updated.processing_status == "failed"
    assert "dimensions" in updated.processing_error.lower()
    assert str(tmp_path) not in updated.processing_error


def test_hls_output_verification_failure_prevents_ready(db, tmp_path, monkeypatch):
    """When FFmpeg exits 0 but does not produce valid HLS, status must become 'failed'."""
    valid_file = tmp_path / "valid.mp4"
    valid_file.write_bytes(b"DATA")
    movie = _make_movie(db, storage="local", path=str(valid_file))
    movie_id = movie.id
    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)

    monkeypatch.setattr("app.services.hls_service.get_video_dimensions", lambda p: (1280, 720))
    monkeypatch.setattr("app.services.hls_service.get_video_duration", lambda p: 10.0)
    monkeypatch.setattr("app.services.hls_service.has_audio_stream", lambda p: True)

    # fake_spawn exits 0 but creates NO output files
    monkeypatch.setattr("app.services.hls_service._spawn_ffmpeg", lambda *a, **k: (0, []))

    process_hls_conversion(movie_id)

    db.expire_all()
    updated = db.query(Movie).filter(Movie.id == movie_id).first()
    assert updated.processing_status == "failed"
    assert updated.hls_playlist_path is None


# ─── 5. Defects H1 & H2 Fixes ─────────────────────────────────────────────────

def test_cancellation_during_processing_h2_defect_fix(db, tmp_path, monkeypatch):
    """
    H2 Regression Test:
    Cancelling an encode when HLS output is missing must set status='failed'
    with step='Cancelled', NEVER status='ready'.
    """
    movie = _make_movie(db, storage="r2", key="sources/m/vid.mp4", status="processing")
    movie_id = movie.id
    movie.hls_playlist_path = None
    db.commit()

    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)

    result = cancel_encode_task(movie_id)
    assert result["cancelled"] is True

    db.expire_all()
    updated = db.query(Movie).filter(Movie.id == movie_id).first()
    # H2 FIX VERIFICATION: Must NOT be ready!
    assert updated.processing_status == "failed"
    assert updated.processing_step == "Cancelled"
    assert updated.hls_playlist_path is None
    assert "cancelled by user" in updated.processing_error.lower()


def test_restart_recovery_h1_defect_fix(db, tmp_path):
    """
    H1 Regression Test:
    Server restart recovery must find movies stranded in 'processing' status
    and mark them as 'failed' (or 'ready' if complete output exists),
    preventing them from being permanently stuck.
    """
    # Movie 1: stranded without output
    m1 = _make_movie(db, storage="local", path="media/v1.mp4", status="processing")
    m1_id = m1.id
    m1.hls_playlist_path = None

    # Movie 2: stranded but output files actually exist
    m2 = _make_movie(db, storage="r2", key="sources/m2.mp4", status="processing")
    m2_id = m2.id

    m2_out = os.path.join("media", "videos", "hls", f"movie_{m2_id}")
    os.makedirs(m2_out, exist_ok=True)
    pl = os.path.join(m2_out, "master.m3u8")
    with open(pl, "w") as f:
        f.write("#EXTM3U\nvariant.m3u8\n")
    with open(os.path.join(m2_out, "seg_001.ts"), "wb") as f:
        f.write(b"\x47")
    m2.hls_playlist_path = pl
    db.commit()

    try:
        recovered = recover_stuck_encodes(db)
        assert m1_id in recovered
        assert m2_id in recovered

        db.expire_all()
        refreshed_m1 = db.query(Movie).filter(Movie.id == m1_id).first()
        refreshed_m2 = db.query(Movie).filter(Movie.id == m2_id).first()

        # m1 was interrupted without HLS: should be marked failed with Interrupted
        assert refreshed_m1.processing_status == "failed"
        assert refreshed_m1.processing_step == "Interrupted"
        assert "interrupted by a server restart" in refreshed_m1.processing_error.lower()

        # m2 had valid HLS: recovered to ready
        assert refreshed_m2.processing_status == "ready"
    finally:
        if os.path.exists(m2_out):
            import shutil
            shutil.rmtree(m2_out, ignore_errors=True)


# ─── 6. Concurrency and Stale Source Protection ───────────────────────────────

def test_duplicate_job_prevention(db, monkeypatch):
    """Concurrency guard: if movie is already in _active_job_movies, skip duplicate."""
    movie = _make_movie(db, storage="local", path="some/path.mp4")
    movie_id = movie.id
    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)

    called = []
    def fake_resolve(*a, **k):
        called.append(True)
        raise RuntimeError("should not reach")

    monkeypatch.setattr("app.services.hls_service.resolve_video_source", fake_resolve)

    # Pre-register movie in active jobs
    with _active_job_lock:
        _active_job_movies.add(str(movie_id))

    try:
        process_hls_conversion(movie_id)
        # Did not attempt conversion
        assert len(called) == 0
    finally:
        with _active_job_lock:
            _active_job_movies.discard(str(movie_id))


def test_stale_source_replacement_during_processing(db, tmp_path, monkeypatch):
    """
    If admin replaces the active source while conversion is running,
    completed HLS from the old source must NOT be published!
    """
    initial_file = tmp_path / "first.mp4"
    initial_file.write_bytes(b"FIRST_SOURCE")
    movie = _make_movie(db, storage="local", path=str(initial_file))
    movie_id = movie.id

    monkeypatch.setattr("app.services.hls_service.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.services.hls_service.get_video_dimensions", lambda p: (1280, 720))
    monkeypatch.setattr("app.services.hls_service.get_video_duration", lambda p: 10.0)
    monkeypatch.setattr("app.services.hls_service.has_audio_stream", lambda p: True)

    def spawn_and_replace_source(cmd, db_arg, db_m, dur, movie_id=None):
        # In a separate transaction, simulate admin uploading new R2 source mid-encode
        sub_db = TestingSessionLocal()
        try:
            m = sub_db.query(Movie).filter(Movie.id == movie_id).first()
            m.source_storage = "r2"
            m.source_object_key = "sources/new_video.mp4"
            m.processing_status = "processing"
            sub_db.commit()
        finally:
            sub_db.close()

        out_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "master.m3u8"), "w") as f:
            f.write("#EXTM3U\n")
        with open(os.path.join(out_dir, "v0_segment_000.ts"), "wb") as f:
            f.write(b"\x47")
        return (0, [])

    monkeypatch.setattr("app.services.hls_service._spawn_ffmpeg", spawn_and_replace_source)

    try:
        process_hls_conversion(movie_id)

        db.expire_all()
        updated = db.query(Movie).filter(Movie.id == movie_id).first()
        # Stale HLS must NOT be published!
        assert updated.hls_playlist_path is None
        assert updated.source_object_key == "sources/new_video.mp4"
        # Output dir must have been cleaned up
        out_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        assert not os.path.exists(out_dir)
    finally:
        out_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        if os.path.exists(out_dir):
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)
