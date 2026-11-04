"""
Admin Metadata Enrichment Router (Phase 8A).

Provides administrative endpoints to:
  1. Trigger a TMDB metadata enrichment staging job for an existing movie
  2. List enrichment attempts / history for a movie
  3. Inspect a specific enrichment job (candidates, conflicts, provenance, review events)
  4. Select a candidate identity for review
  5. Approve selected metadata fields (with optional immediate atomic application)
  6. Explicitly apply an already-approved enrichment job
  7. Reject a metadata enrichment job or candidate

All endpoints require administrator authentication (`get_current_admin_user`).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from .. import database
from ..schemas.metadata_enrichment import (
    ApplyApprovedMetadataRequest,
    CandidateSelectRequest,
    EnrichmentApproveRequest,
    EnrichmentRejectRequest,
    EnrichmentTriggerRequest,
    MetadataEnrichmentJobSchema,
)
from ..services.metadata_application_service import apply_approved_metadata
from ..services.metadata_staging_service import (
    get_enrichment_job,
    list_movie_enrichment_jobs,
    review_approve_enrichment_job,
    review_reject_enrichment_job,
    select_enrichment_candidate,
    serialize_enrichment_job,
    start_enrichment_job,
)
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-metadata-enrichment"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.post(
    "/movies/{movie_id}/enrichment/start",
    response_model=MetadataEnrichmentJobSchema,
    status_code=201,
)
def trigger_movie_enrichment(
    movie_id: UUID,
    payload: EnrichmentTriggerRequest = Body(default_factory=EnrichmentTriggerRequest),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """
    Start a TMDB metadata enrichment staging job for an existing movie.
    Never modifies the `movies` table directly; candidates are staged for review.
    """
    job = start_enrichment_job(
        db=db,
        movie_id=movie_id,
        admin_email=admin_user.email,
        source_language=payload.source_language,
        include_vi_localization=payload.include_vi_localization,
        max_candidates=payload.max_candidates,
    )
    return serialize_enrichment_job(db, job)


@router.get(
    "/movies/{movie_id}/enrichment/jobs",
    response_model=list[MetadataEnrichmentJobSchema],
)
def get_movie_enrichment_history(
    movie_id: UUID,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """List all metadata enrichment jobs and audit trails for a movie (newest first)."""
    return list_movie_enrichment_jobs(db=db, movie_id=movie_id)


@router.get(
    "/enrichment/jobs/{job_id}",
    response_model=MetadataEnrichmentJobSchema,
)
def get_enrichment_job_detail(
    job_id: UUID,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """Retrieve a single metadata enrichment job with candidates, events, and provenances."""
    job = get_enrichment_job(db=db, job_id=job_id)
    return serialize_enrichment_job(db, job)


@router.post(
    "/enrichment/jobs/{job_id}/select-candidate",
    response_model=MetadataEnrichmentJobSchema,
)
def select_candidate_for_job(
    job_id: UUID,
    payload: CandidateSelectRequest,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """Select which TMDB candidate identity to review for an active enrichment job."""
    job = select_enrichment_candidate(
        db=db,
        job_id=job_id,
        candidate_id=payload.candidate_id,
        admin_email=admin_user.email,
        notes=payload.notes,
    )
    return serialize_enrichment_job(db, job)


@router.post(
    "/enrichment/jobs/{job_id}/approve",
    response_model=MetadataEnrichmentJobSchema,
)
def approve_enrichment_job(
    job_id: UUID,
    payload: EnrichmentApproveRequest,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """
    Approve selected metadata fields on a candidate.
    When `apply_immediately=True` (default), atomically applies the approved
    fields to PostgreSQL/SQLite and refreshes the TF-IDF recommendation cache.
    """
    job = review_approve_enrichment_job(
        db=db,
        job_id=job_id,
        candidate_id=payload.candidate_id,
        approved_fields=payload.approved_fields,
        admin_email=admin_user.email,
        allow_overwrite_existing=payload.allow_overwrite_existing,
        expected_metadata_version=payload.expected_metadata_version,
        notes=payload.notes,
    )
    if payload.apply_immediately and job.status != "applied":
        job = apply_approved_metadata(
            db=db,
            job_id=job.id,
            admin_email=admin_user.email,
            expected_metadata_version=payload.expected_metadata_version,
            notes=payload.notes,
        )
    return serialize_enrichment_job(db, job)


@router.post(
    "/enrichment/jobs/{job_id}/apply",
    response_model=MetadataEnrichmentJobSchema,
)
def apply_enrichment_job_endpoint(
    job_id: UUID,
    payload: ApplyApprovedMetadataRequest = Body(
        default_factory=ApplyApprovedMetadataRequest
    ),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """Explicitly apply an already-approved metadata enrichment job."""
    job = apply_approved_metadata(
        db=db,
        job_id=job_id,
        admin_email=admin_user.email,
        expected_metadata_version=payload.expected_metadata_version,
    )
    return serialize_enrichment_job(db, job)


@router.post(
    "/enrichment/jobs/{job_id}/reject",
    response_model=MetadataEnrichmentJobSchema,
)
def reject_enrichment_job_endpoint(
    job_id: UUID,
    payload: EnrichmentRejectRequest,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """Reject a metadata enrichment job or candidate and release the active job lock."""
    job = review_reject_enrichment_job(
        db=db,
        job_id=job_id,
        admin_email=admin_user.email,
        reason=payload.reason,
        candidate_id=payload.candidate_id,
    )
    return serialize_enrichment_job(db, job)
