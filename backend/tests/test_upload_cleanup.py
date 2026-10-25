"""
Tests for the opt-in R2 upload cleanup (service + CLI script).

No destructive R2 operation is performed: every DeleteObject call is answered
by botocore's Stubber, and the Stubber fails the test if an unexpected call
(e.g. a delete in dry-run mode) is attempted.
"""

import importlib.util
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from botocore.stub import Stubber
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.movie import Movie
from app.models.upload_session import UploadSession
from app.models.user import User
from app.services import upload_cleanup_service as cleanup
from app.services.r2_storage_service import R2Settings, R2StorageService

BUCKET = "movsug-cleanup-test-bucket"
NOW = datetime(2026, 10, 25, 12, 0, 0)

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


@pytest.fixture
def storage():
    sleeps = []
    service = R2StorageService(
        R2Settings(
            endpoint_url="https://cleanup-test.r2.cloudflarestorage.com",
            bucket_name=BUCKET,
            access_key_id="FAKEACCESSKEYID",
            secret_access_key="FAKE-SECRET",
        ),
        sleep=sleeps.append,
    )
    stubber = Stubber(service.client)
    stubber.activate()
    yield service, stubber, sleeps
    stubber.assert_no_pending_responses()
    stubber.deactivate()


@pytest.fixture
def owner(db):
    u = User(id=uuid.uuid4(), email="owner@cleanup.test", password_hash="x", role="admin")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def movie(db):
    m = Movie(id=uuid.uuid4(), title="Cleanup Movie")
    db.add(m)
    db.commit()
    return m


def _session(db, movie, owner, status, *, expires_delta=timedelta(hours=-48), key=None):
    sid = uuid.uuid4()
    row = UploadSession(
        id=sid, movie_id=movie.id, created_by_user_id=owner.id,
        object_key=key or f"sources/movie_{movie.id}/{sid}/tok.mp4",
        original_filename="x.mp4", content_type="video/mp4", expected_size=10,
        status=status, created_at=NOW - timedelta(hours=72),
        expires_at=NOW + expires_delta,
    )
    db.add(row)
    db.commit()
    return row


def _expect_delete(stubber, key):
    stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": key})


def _actions(report):
    return {item.session_id: item.action for item in report.items}


# ── Candidate selection ───────────────────────────────────────────────────────

def test_candidates_exclude_completed_recent_pending_and_already_cleaned(db, owner, movie):
    failed = _session(db, movie, owner, "failed")
    expired = _session(db, movie, owner, "expired")
    old_pending = _session(db, movie, owner, "pending", expires_delta=timedelta(hours=-25))
    _session(db, movie, owner, "pending", expires_delta=timedelta(hours=-1))   # within grace
    _session(db, movie, owner, "pending", expires_delta=timedelta(minutes=10))  # still valid
    _session(db, movie, owner, "completed")
    cleaned = _session(db, movie, owner, "failed")
    cleaned.object_deleted_at = NOW
    db.commit()

    ids = {s.id for s in cleanup.find_cleanup_candidates(db, NOW, timedelta(hours=24))}
    assert ids == {failed.id, expired.id, old_pending.id}


# ── Dry run ───────────────────────────────────────────────────────────────────

def test_dry_run_changes_nothing_and_never_calls_r2(db, owner, movie, storage):
    service, _stubber, _ = storage  # no stubbed responses → any R2 call fails
    failed = _session(db, movie, owner, "failed")
    pending = _session(db, movie, owner, "pending")

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=True, now=NOW)

    assert report.dry_run is True
    assert _actions(report) == {str(failed.id): "would_delete", str(pending.id): "would_delete"}
    db.expire_all()
    assert db.get(UploadSession, pending.id).status == "pending"
    assert db.get(UploadSession, failed.id).object_deleted_at is None


def test_dry_run_works_without_storage(db, owner, movie):
    _session(db, movie, owner, "expired")
    report = cleanup.cleanup_abandoned_uploads(db, None, dry_run=True, now=NOW)
    assert report.count("would_delete") == 1


def test_execute_requires_storage(db):
    with pytest.raises(ValueError):
        cleanup.cleanup_abandoned_uploads(db, None, dry_run=False, now=NOW)


# ── Execute ───────────────────────────────────────────────────────────────────

def test_execute_deletes_own_objects_and_expires_abandoned_pending(db, owner, movie, storage):
    service, stubber, _ = storage
    failed = _session(db, movie, owner, "failed")
    pending = _session(db, movie, owner, "pending")
    _expect_delete(stubber, failed.object_key)
    _expect_delete(stubber, pending.object_key)

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)

    assert report.count("deleted") == 2
    db.expire_all()
    p = db.get(UploadSession, pending.id)
    assert p.status == "expired" and p.object_deleted_at == NOW
    assert p.error == cleanup.ABANDONED_REASON
    f = db.get(UploadSession, failed.id)
    assert f.status == "failed" and f.object_deleted_at == NOW

    # Second run: nothing left to do, no further R2 calls.
    assert cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW).items == []


def test_never_deletes_object_referenced_by_a_movie(db, owner, movie, storage):
    service, _stubber, _ = storage
    failed = _session(db, movie, owner, "failed")
    other = Movie(id=uuid.uuid4(), title="Uses that key", source_storage="r2",
                  source_object_key=failed.object_key)
    db.add(other)
    db.commit()

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)
    assert _actions(report) == {str(failed.id): "skipped_referenced"}
    db.expire_all()
    assert db.get(UploadSession, failed.id).object_deleted_at is None


def test_never_deletes_key_outside_session_namespace(db, owner, movie, storage):
    service, _stubber, _ = storage
    foreign_session = uuid.uuid4()
    bad = _session(db, movie, owner, "failed",
                   key=f"sources/movie_{movie.id}/{foreign_session}/tok.mp4")

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)
    assert _actions(report) == {str(bad.id): "skipped_key_mismatch"}


def test_persistent_r2_error_is_reported_and_retried_next_run(db, owner, movie, storage):
    service, stubber, sleeps = storage
    failed = _session(db, movie, owner, "failed")
    for _ in range(3):  # bounded: exactly DEFAULT_MAX_ATTEMPTS attempts
        stubber.add_client_error("delete_object", service_error_code="InternalError",
                                 http_status_code=500)

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)
    assert report.has_errors
    assert _actions(report) == {str(failed.id): "error"}
    assert sleeps == [0.5, 1.0]
    db.expire_all()
    assert db.get(UploadSession, failed.id).object_deleted_at is None


def test_transient_error_then_success(db, owner, movie, storage):
    service, stubber, sleeps = storage
    failed = _session(db, movie, owner, "failed")
    stubber.add_client_error("delete_object", service_error_code="SlowDown", http_status_code=503)
    _expect_delete(stubber, failed.object_key)

    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)
    assert report.count("deleted") == 1
    assert sleeps == [0.5]


def test_pending_completed_concurrently_is_skipped(db, owner, movie, storage, monkeypatch):
    """If a pending session is completed between selection and processing, skip it."""
    service, _stubber, _ = storage
    pending = _session(db, movie, owner, "pending")

    real_find = cleanup.find_cleanup_candidates

    def find_then_complete(*args, **kwargs):
        rows = real_find(*args, **kwargs)
        db.query(UploadSession).filter(UploadSession.id == pending.id).update(
            {"status": "completed"}, synchronize_session=False)
        db.commit()
        return rows

    monkeypatch.setattr(cleanup, "find_cleanup_candidates", find_then_complete)
    report = cleanup.cleanup_abandoned_uploads(db, service, dry_run=False, now=NOW)
    assert _actions(report) == {str(pending.id): "skipped_state_changed"}
    db.expire_all()
    assert db.get(UploadSession, pending.id).status == "completed"


def test_limit_bounds_a_single_run(db, owner, movie):
    for _ in range(5):
        _session(db, movie, owner, "failed")
    report = cleanup.cleanup_abandoned_uploads(db, None, dry_run=True, now=NOW, limit=2)
    assert len(report.items) == 2


# ── CLI script ────────────────────────────────────────────────────────────────

def _load_script():
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "cleanup_r2_uploads.py")
    spec = importlib.util.spec_from_file_location("cleanup_r2_uploads", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_r2_env(monkeypatch):
    for name in ("R2_ENDPOINT", "R2_BUCKET_NAME", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(name, "")


def test_script_defaults_to_dry_run_and_needs_no_r2(db, owner, movie, monkeypatch, capsys):
    script = _load_script()
    _clear_r2_env(monkeypatch)
    monkeypatch.setattr(script, "SessionLocal", TestingSessionLocal)
    expired = _session(db, movie, owner, "expired")

    assert script.main([]) == script.EXIT_OK
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out
    assert f"session={expired.id}" in out
    assert expired.object_key not in out  # keys are not printed
    db.expire_all()
    assert db.get(UploadSession, expired.id).object_deleted_at is None


def test_script_execute_refuses_without_r2(monkeypatch, capsys):
    script = _load_script()
    _clear_r2_env(monkeypatch)
    assert script.main(["--execute"]) == script.EXIT_NOT_CONFIGURED
    assert "Refusing" in capsys.readouterr().out


def test_now_default_is_naive_utc():
    assert cleanup._utcnow().tzinfo is None
    assert abs(cleanup._utcnow() - datetime.now(timezone.utc).replace(tzinfo=None)) < timedelta(seconds=5)
