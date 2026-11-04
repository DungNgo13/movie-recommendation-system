"""
Approved-metadata application service for Phase 8A.

Applies admin-approved candidate metadata from staging tables to the production
`Movie` record inside an atomic database transaction:
  - Updates only `job.approved_fields` from the selected `MetadataCandidate`
  - Enforces optimistic concurrency via `expected_metadata_version`
  - Guarantees idempotency on repeated application calls for the same job
  - Never modifies protected video/upload/streaming or user interaction fields
  - Records field-level provenance (`MetadataFieldProvenance`), review audit
    events (`MetadataReviewEvent`), and admin audit logs (`AdminAuditLog`)
  - Records TMDB image attribution in `MovieAsset` when `poster_path` or
    `backdrop_path` is applied
  - Synchronizes the TF-IDF recommendation cache after commit
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..core.api_errors import (
    CodedHTTPException,
    ENRICHMENT_APPLICATION_FAILED,
    ENRICHMENT_CANDIDATE_NOT_FOUND,
    ENRICHMENT_CONCURRENT_MODIFICATION,
    ENRICHMENT_INVALID_STATE,
    ENRICHMENT_JOB_NOT_FOUND,
    MOVIE_NOT_FOUND,
)
from ..models.admin_audit_log import AdminAuditLog
from ..models.metadata_enrichment import (
    MetadataCandidate,
    MetadataEnrichmentJob,
    MetadataFieldProvenance,
    MetadataReviewEvent,
)
from ..models.movie import Movie
from ..models.movie_asset import MovieAsset
from .metadata_validator import ENRICHABLE_FIELDS, PROTECTED_MOVIE_FIELDS
from .recommendation.vectorizer import invalidate_cache

logger = logging.getLogger(__name__)

TMDB_STATUTORY_ATTRIBUTION = (
    "This product uses the TMDB API but is not endorsed or certified by TMDB."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_movie_field(movie: Movie, field_name: str) -> Any:
    val = getattr(movie, field_name, None)
    if isinstance(val, date):
        return val.isoformat()
    return val


def _coerce_value_for_movie_column(field_name: str, raw_value: Any) -> Any:
    if raw_value is None:
        return None
    if field_name == "release_date":
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, str):
            return date.fromisoformat(raw_value[:10])
    if field_name == "tmdb_id":
        return int(raw_value)
    return raw_value


def _upsert_tmdb_movie_asset(
    db: Session,
    movie_id: UUID,
    asset_type: str,
    url: str,
    tmdb_external_id: str,
) -> None:
    """Record or update per-asset TMDB source & attribution metadata."""
    source_url = f"https://www.themoviedb.org/movie/{tmdb_external_id}"
    existing = (
        db.query(MovieAsset)
        .filter(
            MovieAsset.movie_id == movie_id,
            MovieAsset.asset_type == asset_type,
            MovieAsset.source_name == "TMDB",
        )
        .first()
    )
    if existing is not None:
        existing.url = url
        existing.source_url = source_url
        existing.attribution = TMDB_STATUTORY_ATTRIBUTION
        existing.media_rights_status = "attribution_required"
    else:
        db.add(
            MovieAsset(
                movie_id=movie_id,
                asset_type=asset_type,
                url=url,
                source_name="TMDB",
                source_url=source_url,
                license_type="TMDB API Terms of Use",
                license_url="https://www.themoviedb.org/api-terms-of-use",
                attribution=TMDB_STATUTORY_ATTRIBUTION,
                is_public_domain=False,
                media_rights_status="attribution_required",
            )
        )


def apply_approved_metadata(
    db: Session,
    job_id: UUID,
    admin_email: str,
    expected_metadata_version: int | None = None,
    notes: str | None = None,
) -> MetadataEnrichmentJob:
    """
    Atomically apply approved fields from a staged enrichment job to the
    target `Movie` record, record provenance, and invalidate the TF-IDF
    recommendation cache.

    Idempotency:
      If the job has already been applied (`status == "applied"` and
      `application_status == "applied"`), returns the job immediately without
      creating duplicate provenance rows or bumping `metadata_version`.
    """
    job = (
        db.query(MetadataEnrichmentJob)
        .filter(MetadataEnrichmentJob.id == job_id)
        .first()
    )
    if job is None:
        raise CodedHTTPException(
            status_code=404,
            detail=f"Enrichment job '{job_id}' not found.",
            code=ENRICHMENT_JOB_NOT_FOUND,
        )

    # Idempotent early return for already-applied jobs
    if job.status == "applied" and job.application_status == "applied":
        return job

    if job.status not in ("approved", "partially_approved") or job.review_state not in (
        "approved",
        "partially_approved",
    ):
        raise CodedHTTPException(
            status_code=409,
            detail=(
                f"Job '{job_id}' must be approved before applying "
                f"(current status='{job.status}', review_state='{job.review_state}')."
            ),
            code=ENRICHMENT_INVALID_STATE,
        )

    if not job.selected_candidate_id:
        raise CodedHTTPException(
            status_code=409,
            detail="Cannot apply job without a selected candidate.",
            code=ENRICHMENT_CANDIDATE_NOT_FOUND,
        )

    candidate = (
        db.query(MetadataCandidate)
        .filter(
            MetadataCandidate.id == job.selected_candidate_id,
            MetadataCandidate.job_id == job.id,
        )
        .first()
    )
    if candidate is None:
        raise CodedHTTPException(
            status_code=404,
            detail=f"Selected candidate '{job.selected_candidate_id}' not found.",
            code=ENRICHMENT_CANDIDATE_NOT_FOUND,
        )

    movie = db.query(Movie).filter(Movie.id == job.movie_id).first()
    if movie is None:
        raise CodedHTTPException(
            status_code=404,
            detail=f"Movie '{job.movie_id}' not found.",
            code=MOVIE_NOT_FOUND,
        )

    current_version = int(movie.metadata_version or 1)
    if (
        expected_metadata_version is not None
        and expected_metadata_version != current_version
    ):
        raise CodedHTTPException(
            status_code=409,
            detail=(
                f"Concurrent modification detected for movie '{movie.id}': "
                f"expected metadata_version={expected_metadata_version}, "
                f"found metadata_version={current_version}."
            ),
            code=ENRICHMENT_CONCURRENT_MODIFICATION,
        )

    approved_fields: list[str] = list(job.approved_fields or [])
    proposed_payload: dict[str, Any] = dict(candidate.proposed_fields or {})

    # Defensive guard: never touch protected fields even if somehow present
    for field_name in approved_fields:
        if field_name in PROTECTED_MOVIE_FIELDS or field_name not in ENRICHABLE_FIELDS:
            raise CodedHTTPException(
                status_code=400,
                detail=f"Field '{field_name}' is protected or not enrichable.",
                code=ENRICHMENT_APPLICATION_FAILED,
            )

    now = _utc_now()
    applied_fields: list[str] = []
    all_proposed_keys = [k for k, v in proposed_payload.items() if v is not None]
    rejected_fields = [k for k in all_proposed_keys if k not in approved_fields]
    prev_review_state = job.review_state

    try:
        for field_name in approved_fields:
            if field_name not in proposed_payload:
                continue
            raw_new_val = proposed_payload[field_name]
            if raw_new_val is None:
                continue

            previous_serialized = _serialize_movie_field(movie, field_name)
            coerced_new_val = _coerce_value_for_movie_column(field_name, raw_new_val)
            setattr(movie, field_name, coerced_new_val)
            new_serialized = _serialize_movie_field(movie, field_name)

            db.add(
                MetadataFieldProvenance(
                    movie_id=movie.id,
                    job_id=job.id,
                    candidate_id=candidate.id,
                    field_name=field_name,
                    provider=candidate.provider,
                    provider_movie_id=candidate.provider_movie_id,
                    source_language=candidate.source_language,
                    previous_value=previous_serialized,
                    applied_value=new_serialized,
                    approved_by_email=admin_email,
                    retrieved_at=candidate.retrieved_at or now,
                    applied_at=now,
                )
            )
            applied_fields.append(field_name)

            if field_name == "poster_path" and isinstance(coerced_new_val, str):
                _upsert_tmdb_movie_asset(
                    db=db,
                    movie_id=movie.id,
                    asset_type="poster",
                    url=coerced_new_val,
                    tmdb_external_id=candidate.provider_movie_id,
                )
            elif field_name == "backdrop_path" and isinstance(coerced_new_val, str):
                _upsert_tmdb_movie_asset(
                    db=db,
                    movie_id=movie.id,
                    asset_type="backdrop",
                    url=coerced_new_val,
                    tmdb_external_id=candidate.provider_movie_id,
                )

        # Ensure TMDB source attribution is recorded on the movie when fields are applied
        if applied_fields:
            if not movie.source_name:
                movie.source_name = "TMDB"
            if not movie.source_url:
                movie.source_url = (
                    f"https://www.themoviedb.org/movie/{candidate.provider_movie_id}"
                )
            if not movie.attribution:
                movie.attribution = TMDB_STATUTORY_ATTRIBUTION
            elif TMDB_STATUTORY_ATTRIBUTION not in movie.attribution:
                movie.attribution = (
                    f"{movie.attribution.rstrip()} | {TMDB_STATUTORY_ATTRIBUTION}"
                )

        movie.metadata_version = current_version + 1

        job.status = "applied"
        job.application_status = "applied"
        job.active_lock = None
        job.applied_at = now
        job.updated_at = now

        db.add(
            MetadataReviewEvent(
                job_id=job.id,
                movie_id=movie.id,
                candidate_id=candidate.id,
                reviewing_admin_email=admin_email,
                action="apply_approved",
                review_state_before=prev_review_state,
                review_state_after=job.review_state,
                approved_fields=applied_fields,
                rejected_fields=rejected_fields,
                notes=notes
                or (
                    f"Applied {len(applied_fields)} field(s) from TMDB #{candidate.provider_movie_id}; "
                    f"metadata_version {current_version} -> {movie.metadata_version}"
                ),
                created_at=now,
            )
        )

        db.add(
            AdminAuditLog(
                admin_user_email=admin_email,
                action_type="movie_metadata_enrichment_apply",
                target_type="movie",
                target_id=str(movie.id),
                description=(
                    f"Applied TMDB #{candidate.provider_movie_id} metadata fields "
                    f"{applied_fields} to '{movie.title}' (v{movie.metadata_version})"
                ),
                created_at=now,
            )
        )

        db.commit()
        db.refresh(job)
    except CodedHTTPException:
        db.rollback()
        raise
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        db.rollback()
        logger.error("Failed applying enrichment job %s: %s", job_id, exc)
        try:
            failed_job = (
                db.query(MetadataEnrichmentJob)
                .filter(MetadataEnrichmentJob.id == job_id)
                .first()
            )
            if failed_job is not None:
                failed_job.application_status = "rolled_back"
                failed_job.failure_reason = f"[{ENRICHMENT_APPLICATION_FAILED}] {str(exc)[:400]}"
                failed_job.updated_at = _utc_now()
                db.commit()
        except Exception:
            db.rollback()

        raise CodedHTTPException(
            status_code=500,
            detail="Database transaction failed while applying approved metadata; changes were rolled back.",
            code=ENRICHMENT_APPLICATION_FAILED,
        ) from exc

    # Synchronize recommendation cache only after transaction commits cleanly
    invalidate_cache()
    return job
