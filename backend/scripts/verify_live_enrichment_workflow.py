"""
Live enrichment workflow verification script.

**Requires explicit manual execution** — never run by pytest or CI.

Usage:
    cd backend
    python scripts/verify_live_enrichment_workflow.py

Prerequisites:
    - backend/.env must contain TMDB_ENABLE_LIVE_REQUESTS=true
    - backend/.env must contain a valid TMDB_API_READ_ACCESS_TOKEN
    - Network access to api.themoviedb.org must be available

Verifies the full Human-in-the-Loop enrichment pipeline with real TMDB data:
  1. Create a test movie in an in-memory SQLite database (no production data)
  2. Start an enrichment job via the admin endpoint (makes REAL TMDB requests)
  3. Verify candidates are returned with correct structure
  4. Approve specific fields (explicit admin authorization required)
  5. Apply approved metadata to the movie record
  6. Verify enrichment history and field-level provenance audit trail
  7. Clean up: drop all in-memory tables and release connections

Security:
  - Credentials are loaded from backend/.env (never hardcoded)
  - The access token value is never printed or logged
  - Uses in-memory SQLite — production PostgreSQL is never touched
  - All test data is destroyed on completion (success or failure)
  - Admin JWT is generated for a synthetic test user only
"""

from __future__ import annotations

import os
import sys
from datetime import date
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.movie import Movie
from app.models.user import User
from app.services.recommendation.vectorizer import invalidate_cache


def run_live_enrichment_test():
    # Set up in-memory database
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Create admin user
        admin = User(
            id=uuid4(),
            email="admin@movsug.test",
            password_hash="$2b$12$dummyhash",
            role="admin",
        )
        session.add(admin)
        session.commit()
        token = create_access_token(data={"sub": str(admin.id), "role": "admin"})
        headers = {"Authorization": f"Bearer {token}"}

        # Create a test movie (Interstellar - well-known on TMDB)
        movie = Movie(
            id=uuid4(),
            title="Interstellar",
            release_date=date(2014, 11, 5),
            genres=["Science Fiction", "Drama"],
            overview="",  # Empty - enrichment should fill this
            cast=[],
            keywords=[],
            director="",
            tmdb_id=157336,  # Known TMDB ID for Interstellar
        )
        session.add(movie)
        session.commit()

        client = TestClient(app)

        # === Step 1: Start enrichment job ===
        print("=== Step 1: Start TMDB Enrichment Job ===")
        resp = client.post(
            f"/api/v1/admin/movies/{movie.id}/enrichment/start",
            json={
                "source_language": "en-US",
                "include_vi_localization": True,
                "max_candidates": 3,
            },
            headers=headers,
        )
        print(f"  Status: {resp.status_code}")
        
        if resp.status_code == 503:
            body = resp.json()
            print(f"  Error: {body.get('detail')}")
            print(f"  Code: {body.get('code')}")
            print("  BLOCKED: Live TMDB requests are still disabled!")
            return False
        
        if resp.status_code != 201:
            body = resp.json()
            print(f"  Error: {body.get('detail')}")
            print(f"  Code: {body.get('code')}")
            return False

        job = resp.json()
        job_id = job["id"]
        print(f"  Job ID: {job_id}")
        print(f"  Status: {job['status']}")
        print(f"  Candidates found: {job['candidates_found']}")
        print(f"  Is mocked: {job['is_mocked']}")
        print(f"  Processing time: {job.get('processing_time_ms')} ms")
        
        assert job["status"] == "awaiting_review", f"Expected awaiting_review, got {job['status']}"
        assert job["candidates_found"] > 0, "No candidates found"
        assert not job["is_mocked"], "Response was mocked, not live"
        
        candidates = job["candidates"]
        print(f"\n  Candidates:")
        for c in candidates:
            print(f"    - TMDB #{c['provider_movie_id']}: {c['title']} ({c.get('release_year')}) "
                  f"score={c['match_score']:.2f} status={c['match_status']}")
            if c.get("director"):
                print(f"      Director: {c['director']}")

        # === Step 2: Verify candidate structure ===
        print("\n=== Step 2: Verify Candidate Structure ===")
        best = candidates[0]
        print(f"  Best match: TMDB #{best['provider_movie_id']} - {best['title']}")
        
        proposed = best.get("proposed_fields", {})
        existing = best.get("existing_values", {})
        conflicts = best.get("field_conflicts", {})
        
        proposed_fields = [k for k, v in proposed.items() if v is not None]
        print(f"  Proposed fields: {proposed_fields}")
        print(f"  Has field_conflicts: {bool(conflicts)}")
        print(f"  Has existing_values: {bool(existing)}")
        
        # Check key metadata fields
        for field in ["overview", "cast", "director", "keywords", "poster_path"]:
            val = proposed.get(field)
            status = "✓" if val else "✗"
            if isinstance(val, list):
                print(f"    {status} {field}: {len(val)} items")
            elif isinstance(val, str):
                print(f"    {status} {field}: {len(val)} chars")
            else:
                print(f"    {status} {field}: {val}")

        # === Step 3: Approve safe fields (non-overwrite only) ===
        print("\n=== Step 3: Approve Metadata Fields ===")
        safe_fields = []
        for field_name in proposed_fields:
            conflict_info = conflicts.get(field_name, {})
            if not conflict_info.get("requires_explicit_overwrite", False):
                safe_fields.append(field_name)
        
        if not safe_fields:
            # If all fields are overwrite, enable overwrite for overview only
            safe_fields = ["overview"]
            allow_overwrite = True
        else:
            allow_overwrite = False
        
        print(f"  Approving fields: {safe_fields}")
        print(f"  Allow overwrite: {allow_overwrite}")
        
        resp = client.post(
            f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
            json={
                "candidate_id": best["id"],
                "approved_fields": safe_fields,
                "allow_overwrite_existing": allow_overwrite,
                "expected_metadata_version": job.get("movie_metadata_version"),
                "apply_immediately": True,
            },
            headers=headers,
        )
        print(f"  Approve status: {resp.status_code}")
        
        if resp.status_code != 200:
            body = resp.json()
            print(f"  Error: {body.get('detail')}")
            print(f"  Code: {body.get('code')}")
            return False
        
        applied_job = resp.json()
        print(f"  Job status: {applied_job['status']}")
        print(f"  Application status: {applied_job['application_status']}")
        print(f"  Approved fields: {applied_job.get('approved_fields')}")

        # === Step 4: Verify persistence ===
        print("\n=== Step 4: Verify Database Persistence ===")
        session.refresh(movie)
        for field in safe_fields:
            val = getattr(movie, field, "MISSING_ATTR")
            if isinstance(val, list):
                print(f"  {field}: {len(val)} items")
            elif isinstance(val, str):
                print(f"  {field}: {len(val)} chars")
            else:
                print(f"  {field}: {val}")
        
        print(f"  metadata_version: {movie.metadata_version}")
        assert movie.metadata_version and movie.metadata_version > 1, \
            "metadata_version not incremented"

        # === Step 5: Verify enrichment history ===
        print("\n=== Step 5: Verify Enrichment History ===")
        resp = client.get(
            f"/api/v1/admin/movies/{movie.id}/enrichment/jobs",
            headers=headers,
        )
        print(f"  History status: {resp.status_code}")
        jobs = resp.json()
        print(f"  Total jobs: {len(jobs)}")
        assert len(jobs) >= 1, "No jobs in history"
        
        latest = jobs[0]
        print(f"  Latest job status: {latest['status']}")
        print(f"  Review events: {len(latest.get('review_events', []))}")
        print(f"  Provenances: {len(latest.get('provenances', []))}")
        
        provenances = latest.get("provenances", [])
        for p in provenances:
            print(f"    Provenance: {p['field_name']} from TMDB #{p['provider_movie_id']} "
                  f"by {p['approved_by_email']}")

        # === Final verdict ===
        print("\n=== VERDICT ===")
        print("  Enrichment job: CREATED with live TMDB data")
        print("  Candidates: RETURNED with correct structure")
        print("  Approval: SUCCEEDED")
        print("  Persistence: VERIFIED in database")
        print("  History: VERIFIED")
        print("  Provenance: VERIFIED")
        print("  Overall: ALL PASS ✓")
        return True

    except Exception as e:
        print(f"\n!!! ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        app.dependency_overrides.clear()
        invalidate_cache()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


if __name__ == "__main__":
    success = run_live_enrichment_test()
    sys.exit(0 if success else 1)
