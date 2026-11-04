"""
Metadata enrichment staging and administrative review service (Phase 8A).

Responsibilities:
  - Orchestrates TMDB identity matching, detail retrieval, and field-level validation.
  - Persists `MetadataEnrichmentJob` and `MetadataCandidate` rows in staging tables
    WITHOUT modifying any field on `Movie`.
  - Prevents duplicate concurrent jobs via `active_lock` uniqueness.
  - Records review decisions (`select_candidate`, `approve_fields`, `reject_job`)
    and immutable `MetadataReviewEvent` audit records.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import time
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.api_errors import (
    CodedHTTPException,
    ENRICHMENT_CANDIDATE_NOT_FOUND,
    ENRICHMENT_CONCURRENT_MODIFICATION,
    ENRICHMENT_DUPLICATE_ACTIVE_JOB,
    ENRICHMENT_INVALID_STATE,
    ENRICHMENT_JOB_NOT_FOUND,
    ENRICHMENT_VALIDATION_FAILED,
    MOVIE_NOT_FOUND,
    TMDB_NOT_FOUND,
)
from ..models.metadata_enrichment import (
    MetadataCandidate,
    MetadataEnrichmentJob,
    MetadataFieldProvenance,
    MetadataReviewEvent,
)
from ..models.movie import Movie
from .metadata_matcher import evaluate_and_rank_candidates, parse_movsug_movie_identity
from .metadata_validator import (
    ENRICHABLE_FIELDS,
    MetadataValidationError,
    compare_existing_and_proposed,
    extract_and_validate_tmdb_fields,
    snapshot_existing_movie_fields,
    validate_proposed_field_value,
)
from .tmdb_client import TMDBClient, TMDBClientError

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fetch_candidate_pool_from_tmdb(
    movie: Movie,
    client: TMDBClient,
    source_language: str,
    max_candidates: int,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """
    Retrieve candidate TMDB movie detail payloads for a MovSug `Movie`.

    Priority order:
      1. Existing `movie.tmdb_id` -> direct `get_movie_details(tmdb_id)`
      2. Verified external IDs (`imdb_id` or `wikidata_id`) -> `find_by_external_id`
      3. Title search (`search_movies`) using normalized primary/secondary titles
         (both with and without year filter so remakes and ±1 year offsets are captured).
    """
    identity = parse_movsug_movie_identity(movie)
    candidate_ids: list[int] = []
    external_id_matches: dict[int, str] = {}
    detailed_by_id: dict[int, dict[str, Any]] = {}

    # 1. Direct TMDB ID lookup
    if identity.tmdb_id is not None:
        try:
            detail = client.get_movie_details(identity.tmdb_id, language=source_language)
            cid = int(detail["id"])
            detailed_by_id[cid] = detail
            candidate_ids.append(cid)
            external_id_matches[cid] = f"tmdb_id:{identity.tmdb_id}"
        except TMDBClientError as exc:
            if exc.code != TMDB_NOT_FOUND:
                raise

    # 2. IMDb ID / Wikidata ID lookup
    for ext_id, ext_source in (
        (identity.imdb_id, "imdb_id"),
        (identity.wikidata_id, "wikidata_id"),
    ):
        if not ext_id:
            continue
        found_items = client.find_by_external_id(
            ext_id, external_source=ext_source, language=source_language
        )
        for item in found_items:
            cid = item.get("id")
            if isinstance(cid, int) and cid > 0:
                external_id_matches.setdefault(cid, f"{ext_source}:{ext_id}")
                if cid not in candidate_ids:
                    candidate_ids.append(cid)

    # 3. Title search (run when we don't have a verified ID or to surface remakes/alternatives)
    if not candidate_ids:
        for query in identity.search_queries[:2]:
            # First search without year restriction so remakes (e.g. Nosferatu 1922/1979/2024)
            # and conflicting-year candidates are always discovered for explainable comparison.
            search_res = client.search_movies(query, year=None, language=source_language, page=1)
            for item in search_res.get("results", []):
                cid = item.get("id")
                if isinstance(cid, int) and cid > 0 and cid not in candidate_ids:
                    candidate_ids.append(cid)
                if len(candidate_ids) >= max_candidates:
                    break

            # If year is known and we still have room, also query with year filter
            if identity.release_year and len(candidate_ids) < max_candidates:
                year_res = client.search_movies(
                    query, year=identity.release_year, language=source_language, page=1
                )
                for item in year_res.get("results", []):
                    cid = item.get("id")
                    if isinstance(cid, int) and cid > 0 and cid not in candidate_ids:
                        candidate_ids.append(cid)
                    if len(candidate_ids) >= max_candidates:
                        break

            if len(candidate_ids) >= max_candidates:
                break

    # Fetch full details for top unique candidate IDs
    detailed_candidates: list[dict[str, Any]] = []
    for cid in candidate_ids[:max_candidates]:
        if cid in detailed_by_id:
            detailed_candidates.append(detailed_by_id[cid])
            continue
        try:
            detail = client.get_movie_details(cid, language=source_language)
            detailed_candidates.append(detail)
        except TMDBClientError as exc:
            if exc.code == TMDB_NOT_FOUND:
                continue
            raise

    return detailed_candidates, external_id_matches


def start_enrichment_job(
    db: Session,
    movie_id: UUID,
    admin_email: str,
    tmdb_client: Optional[TMDBClient] = None,
    source_language: str = "en-US",
    include_vi_localization: bool = True,
    max_candidates: int = 5,
) -> MetadataEnrichmentJob:
    """
    Start a staged TMDB metadata enrichment job for `movie_id`.

    Never writes proposed values directly into `Movie`.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if movie is None:
        raise CodedHTTPException(
            status_code=404,
            detail="Movie not found.",
            code=MOVIE_NOT_FOUND,
        )

    lock_key = f"{movie.id}:tmdb"
    existing_active = (
        db.query(MetadataEnrichmentJob)
        .filter(MetadataEnrichmentJob.active_lock == lock_key)
        .first()
    )
    if existing_active is not None:
        raise CodedHTTPException(
            status_code=409,
            detail=(
                f"An active metadata enrichment job ({existing_active.id}) already exists "
                f"for this movie in status '{existing_active.status}'. "
                "Approve, apply, or reject it before starting a new job."
            ),
            code=ENRICHMENT_DUPLICATE_ACTIVE_JOB,
        )

    owns_client = tmdb_client is None
    client = tmdb_client or TMDBClient()
    start_time = time.monotonic()

    job = MetadataEnrichmentJob(
        movie_id=movie.id,
        provider="tmdb",
        source_language=source_language,
        status="pending",
        active_lock=lock_key,
        review_state="pending_review",
        application_status="not_applied",
        initiated_by_email=admin_email,
        is_mocked=bool(
            getattr(client, "is_mocked", False)
            or getattr(client, "_transport", None) is not None
        ),
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if owns_client:
            client.close()
        raise CodedHTTPException(
            status_code=409,
            detail="Concurrent active enrichment job detected for this movie.",
            code=ENRICHMENT_DUPLICATE_ACTIVE_JOB,
        ) from None

    try:
        detailed_raw, external_matches = _fetch_candidate_pool_from_tmdb(
            movie=movie,
            client=client,
            source_language=source_language,
            max_candidates=max_candidates,
        )
        ranked_matches = evaluate_and_rank_candidates(
            movie=movie,
            candidates=detailed_raw,
            external_id_matches=external_matches,
        )
        raw_by_id = {int(d["id"]): d for d in detailed_raw if "id" in d}
        existing_snapshot = snapshot_existing_movie_fields(movie)

        staged_candidates: list[MetadataCandidate] = []
        for idx, match_res in enumerate(ranked_matches):
            raw_detail = raw_by_id.get(match_res.tmdb_id, {})
            localized_vi: Optional[dict[str, Any]] = None
            if include_vi_localization:
                try:
                    localized_vi = client.get_movie_localized_details(
                        match_res.tmdb_id, language="vi-VN"
                    )
                except TMDBClientError:
                    localized_vi = None

            proposed_fields = extract_and_validate_tmdb_fields(
                raw_detail, localized_vi=localized_vi
            )
            field_conflicts = compare_existing_and_proposed(existing_snapshot, proposed_fields)

            parsed_rd: Optional[date] = None
            if match_res.release_date:
                try:
                    parsed_rd = date.fromisoformat(match_res.release_date[:10])
                except ValueError:
                    parsed_rd = None

            cand_row = MetadataCandidate(
                job_id=job.id,
                movie_id=movie.id,
                provider="tmdb",
                provider_movie_id=str(match_res.tmdb_id),
                source_language=source_language,
                title=match_res.title or movie.title,
                original_title=match_res.original_title,
                release_date=parsed_rd,
                release_year=match_res.release_year,
                original_language=match_res.original_language,
                director=match_res.director,
                match_score=match_res.match_score,
                match_status=match_res.match_status,
                is_verified_id_match=match_res.is_verified_id_match,
                match_evidence=match_res.match_evidence,
                conflicts=match_res.conflicts,
                reason_for_review=match_res.reason_for_review,
                proposed_fields=proposed_fields,
                existing_values=existing_snapshot,
                field_conflicts=field_conflicts,
                review_state="selected" if idx == 0 else "pending",
            )
            db.add(cand_row)
            staged_candidates.append(cand_row)

        db.flush()

        elapsed_ms = round((time.monotonic() - start_time) * 1000.0, 2)
        job.processing_time_ms = elapsed_ms
        job.retry_count = client.stats.retry_count
        job.http_429_count = client.stats.http_429_count
        job.candidates_found = len(staged_candidates)

        if staged_candidates:
            job.status = "awaiting_review"
            job.review_state = "pending_review"
            job.selected_candidate_id = staged_candidates[0].id
        else:
            job.status = "no_match"
            job.review_state = "not_applicable"
            job.active_lock = None  # Terminal state: allow future attempts

        job.updated_at = _utc_now_naive()
        db.commit()
        db.refresh(job)
        return job

    except TMDBClientError as exc:
        elapsed_ms = round((time.monotonic() - start_time) * 1000.0, 2)
        job.status = "failed"
        job.review_state = "not_applicable"
        job.application_status = "not_applied"
        job.failure_reason = f"[{exc.code}] {exc.message}"
        job.active_lock = None
        job.processing_time_ms = elapsed_ms
        job.retry_count = client.stats.retry_count
        job.http_429_count = client.stats.http_429_count
        job.updated_at = _utc_now_naive()
        db.commit()

        http_status = 502
        if exc.status_code in (401, 403):
            http_status = 502
        elif exc.status_code == 429:
            http_status = 429
        elif exc.code in ("tmdb_not_configured", "tmdb_live_requests_disabled"):
            http_status = 503

        raise CodedHTTPException(
            status_code=http_status,
            detail=exc.message,
            code=exc.code,
        ) from None
    finally:
        if owns_client:
            client.close()


def serialize_enrichment_job(db: Session, job: MetadataEnrichmentJob) -> dict[str, Any]:
    """Assemble a complete dict representation of a job with candidates, events, and provenances."""
    candidates = (
        db.query(MetadataCandidate)
        .filter(MetadataCandidate.job_id == job.id)
        .order_by(MetadataCandidate.match_score.desc(), MetadataCandidate.retrieved_at.asc())
        .all()
    )
    review_events = (
        db.query(MetadataReviewEvent)
        .filter(MetadataReviewEvent.job_id == job.id)
        .order_by(MetadataReviewEvent.created_at.asc())
        .all()
    )
    provenances = (
        db.query(MetadataFieldProvenance)
        .filter(MetadataFieldProvenance.job_id == job.id)
        .order_by(MetadataFieldProvenance.applied_at.asc())
        .all()
    )
    movie = db.query(Movie).filter(Movie.id == job.movie_id).first()

    return {
        "id": job.id,
        "movie_id": job.movie_id,
        "provider": job.provider,
        "source_language": job.source_language,
        "status": job.status,
        "selected_candidate_id": job.selected_candidate_id,
        "review_state": job.review_state,
        "initiated_by_email": job.initiated_by_email,
        "reviewing_admin_email": job.reviewing_admin_email,
        "reviewed_at": job.reviewed_at,
        "application_status": job.application_status,
        "applied_at": job.applied_at,
        "failure_reason": job.failure_reason,
        "approved_fields": job.approved_fields,
        "candidates_found": job.candidates_found,
        "retry_count": job.retry_count,
        "http_429_count": job.http_429_count,
        "processing_time_ms": job.processing_time_ms,
        "is_mocked": job.is_mocked,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "candidates": candidates,
        "review_events": review_events,
        "provenances": provenances,
        "movie_metadata_version": getattr(movie, "metadata_version", 1) if movie else None,
    }


def get_enrichment_job(db: Session, job_id: UUID) -> MetadataEnrichmentJob:
    """Fetch a single `MetadataEnrichmentJob` or raise 404."""
    job = db.query(MetadataEnrichmentJob).filter(MetadataEnrichmentJob.id == job_id).first()
    if job is None:
        raise CodedHTTPException(
            status_code=404,
            detail="Metadata enrichment job not found.",
            code=ENRICHMENT_JOB_NOT_FOUND,
        )
    return job


def list_movie_enrichment_jobs(db: Session, movie_id: UUID) -> list[dict[str, Any]]:
    """Return all enrichment jobs for a movie (newest first)."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if movie is None:
        raise CodedHTTPException(
            status_code=404,
            detail="Movie not found.",
            code=MOVIE_NOT_FOUND,
        )
    jobs = (
        db.query(MetadataEnrichmentJob)
        .filter(MetadataEnrichmentJob.movie_id == movie_id)
        .order_by(MetadataEnrichmentJob.created_at.desc())
        .all()
    )
    return [serialize_enrichment_job(db, j) for j in jobs]


def select_enrichment_candidate(
    db: Session,
    job_id: UUID,
    candidate_id: UUID,
    admin_email: str,
    notes: Optional[str] = None,
) -> MetadataEnrichmentJob:
    """Allow an administrator to select a specific candidate identity on a staged job."""
    job = get_enrichment_job(db, job_id)
    if job.status in ("applied", "rejected", "failed", "no_match"):
        raise CodedHTTPException(
            status_code=409,
            detail=f"Cannot change candidate selection when job is in state '{job.status}'.",
            code=ENRICHMENT_INVALID_STATE,
        )

    candidates = (
        db.query(MetadataCandidate)
        .filter(MetadataCandidate.job_id == job.id)
        .all()
    )
    target = next((c for c in candidates if c.id == candidate_id), None)
    if target is None:
        raise CodedHTTPException(
            status_code=404,
            detail="Candidate not found for this enrichment job.",
            code=ENRICHMENT_CANDIDATE_NOT_FOUND,
        )

    prev_state = job.review_state
    for c in candidates:
        c.review_state = "selected" if c.id == candidate_id else "pending"

    job.selected_candidate_id = target.id
    job.updated_at = _utc_now_naive()

    event = MetadataReviewEvent(
        job_id=job.id,
        movie_id=job.movie_id,
        candidate_id=target.id,
        reviewing_admin_email=admin_email,
        action="select_candidate",
        review_state_before=prev_state,
        review_state_after=job.review_state,
        notes=notes,
    )
    db.add(event)
    db.commit()
    db.refresh(job)
    return job


def review_approve_enrichment_job(
    db: Session,
    job_id: UUID,
    candidate_id: UUID,
    approved_fields: list[str],
    admin_email: str,
    allow_overwrite_existing: bool = False,
    expected_metadata_version: Optional[int] = None,
    notes: Optional[str] = None,
) -> MetadataEnrichmentJob:
    """
    Validate and record administrative approval of selected metadata fields.
    Does not write to `Movie` directly — `apply_approved_metadata` performs the
    transactional PostgreSQL/SQLite update.
    """
    job = get_enrichment_job(db, job_id)
    if job.status == "applied":
        # Idempotent if same candidate and fields are already applied
        if job.selected_candidate_id == candidate_id and sorted(job.approved_fields or []) == sorted(approved_fields):
            return job
        raise CodedHTTPException(
            status_code=409,
            detail="Job has already been applied with different parameters.",
            code=ENRICHMENT_INVALID_STATE,
        )
    if job.status in ("rejected", "failed", "no_match"):
        raise CodedHTTPException(
            status_code=409,
            detail=f"Cannot approve a job in status '{job.status}'.",
            code=ENRICHMENT_INVALID_STATE,
        )

    if expected_metadata_version is not None:
        movie = db.query(Movie).filter(Movie.id == job.movie_id).first()
        current_version = int(getattr(movie, "metadata_version", 1) or 1) if movie else 1
        if expected_metadata_version != current_version:
            raise CodedHTTPException(
                status_code=409,
                detail=(
                    f"Concurrent modification detected for movie '{job.movie_id}': "
                    f"expected metadata_version={expected_metadata_version}, "
                    f"found metadata_version={current_version}."
                ),
                code=ENRICHMENT_CONCURRENT_MODIFICATION,
            )

    candidate = (
        db.query(MetadataCandidate)
        .filter(
            MetadataCandidate.id == candidate_id,
            MetadataCandidate.job_id == job.id,
        )
        .first()
    )
    if candidate is None:
        raise CodedHTTPException(
            status_code=404,
            detail="Candidate not found for this enrichment job.",
            code=ENRICHMENT_CANDIDATE_NOT_FOUND,
        )

    # Deduplicate and validate every requested field
    dedup_fields: list[str] = []
    for f in approved_fields:
        if f not in dedup_fields:
            dedup_fields.append(f)

    proposed = candidate.proposed_fields or {}
    field_conflicts = candidate.field_conflicts or {}

    for field_name in dedup_fields:
        if field_name not in ENRICHABLE_FIELDS:
            raise CodedHTTPException(
                status_code=422,
                detail=f"Field '{field_name}' is not an enrichable movie metadata field.",
                code=ENRICHMENT_VALIDATION_FAILED,
            )
        if field_name not in proposed or proposed[field_name] is None:
            raise CodedHTTPException(
                status_code=422,
                detail=f"Candidate does not propose a value for field '{field_name}'.",
                code=ENRICHMENT_VALIDATION_FAILED,
            )
        try:
            validate_proposed_field_value(field_name, proposed[field_name])
        except MetadataValidationError as exc:
            raise CodedHTTPException(
                status_code=422,
                detail=str(exc),
                code=ENRICHMENT_VALIDATION_FAILED,
            ) from None

        conflict_info = field_conflicts.get(field_name, {})
        if conflict_info.get("requires_explicit_overwrite") and not allow_overwrite_existing:
            raise CodedHTTPException(
                status_code=409,
                detail=(
                    f"Field '{field_name}' already has an existing value in MovSug. "
                    "Set allow_overwrite_existing=true to confirm replacing existing data."
                ),
                code=ENRICHMENT_VALIDATION_FAILED,
            )

    all_proposed_keys = [k for k, v in proposed.items() if v is not None]
    rejected_fields = [k for k in all_proposed_keys if k not in dedup_fields]

    prev_state = job.review_state
    new_review_state = "approved" if not rejected_fields else "partially_approved"

    job.selected_candidate_id = candidate.id
    job.approved_fields = dedup_fields
    job.review_state = new_review_state
    job.status = new_review_state
    job.reviewing_admin_email = admin_email
    job.reviewed_at = _utc_now_naive()
    job.updated_at = _utc_now_naive()

    # Mark candidate states
    all_candidates = (
        db.query(MetadataCandidate)
        .filter(MetadataCandidate.job_id == job.id)
        .all()
    )
    for c in all_candidates:
        c.review_state = "approved" if c.id == candidate.id else "rejected"

    event = MetadataReviewEvent(
        job_id=job.id,
        movie_id=job.movie_id,
        candidate_id=candidate.id,
        reviewing_admin_email=admin_email,
        action="approve_fields",
        review_state_before=prev_state,
        review_state_after=new_review_state,
        approved_fields=dedup_fields,
        rejected_fields=rejected_fields,
        notes=notes,
    )
    db.add(event)
    db.commit()
    db.refresh(job)
    return job


def review_reject_enrichment_job(
    db: Session,
    job_id: UUID,
    admin_email: str,
    reason: str,
    candidate_id: Optional[UUID] = None,
) -> MetadataEnrichmentJob:
    """
    Reject a metadata enrichment job (or specific candidate), releasing the active lock
    and recording an immutable review event without modifying the movie.
    """
    job = get_enrichment_job(db, job_id)
    if job.status == "applied":
        raise CodedHTTPException(
            status_code=409,
            detail="Cannot reject an enrichment job that has already been applied.",
            code=ENRICHMENT_INVALID_STATE,
        )
    if job.status == "rejected":
        return job

    prev_state = job.review_state
    job.status = "rejected"
    job.review_state = "rejected"
    job.application_status = "not_applied"
    job.reviewing_admin_email = admin_email
    job.reviewed_at = _utc_now_naive()
    job.active_lock = None
    job.updated_at = _utc_now_naive()

    all_candidates = (
        db.query(MetadataCandidate)
        .filter(MetadataCandidate.job_id == job.id)
        .all()
    )
    for c in all_candidates:
        if candidate_id is None or c.id == candidate_id:
            c.review_state = "rejected"

    event = MetadataReviewEvent(
        job_id=job.id,
        movie_id=job.movie_id,
        candidate_id=candidate_id or job.selected_candidate_id,
        reviewing_admin_email=admin_email,
        action="reject_job",
        review_state_before=prev_state,
        review_state_after="rejected",
        notes=reason.strip(),
    )
    db.add(event)
    db.commit()
    db.refresh(job)
    return job
