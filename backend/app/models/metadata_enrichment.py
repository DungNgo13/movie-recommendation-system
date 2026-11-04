"""
SQLAlchemy models for Movie Metadata Enrichment staging, provenance, and review (Phase 8A).

Entities:
  - MetadataEnrichmentJob      (`metadata_enrichment_jobs`)
  - MetadataCandidate          (`metadata_candidates`)
  - MetadataFieldProvenance    (`metadata_field_provenances`)
  - MetadataReviewEvent        (`metadata_review_events`)

All external provider data is staged here first and never written directly into
`movies` during retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from ..database import Base


def _utc_now_naive() -> datetime:
    """Return current UTC timestamp (naive, matching existing SQLAlchemy models)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MetadataEnrichmentJob(Base):
    """Tracks a metadata enrichment job for a single MovSug movie."""

    __tablename__ = "metadata_enrichment_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(30), nullable=False, default="tmdb", server_default="tmdb")
    source_language = Column(String(16), nullable=False, default="en-US", server_default="en-US")

    # Job lifecycle state:
    #   pending | awaiting_review | no_match | approved | partially_approved | rejected | applied | failed
    status = Column(String(30), nullable=False, default="pending", server_default="pending")

    # Non-null (`"{movie_id}:{provider}"`) only while the job is active (`pending` or
    # `awaiting_review` or `approved` / `partially_approved` awaiting application).
    # Cleared to NULL when terminal (`applied`, `rejected`, `no_match`, `failed`).
    # Enforces at the DB level that at most one active job exists per (movie_id, provider).
    active_lock = Column(String(100), nullable=True)

    selected_candidate_id = Column(UUID(as_uuid=True), nullable=True)

    # Review & application tracking
    review_state = Column(
        String(30), nullable=False, default="pending_review", server_default="pending_review"
    )  # pending_review | approved | partially_approved | rejected | not_applicable
    initiated_by_email = Column(String(255), nullable=True)
    reviewing_admin_email = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    application_status = Column(
        String(30), nullable=False, default="not_applied", server_default="not_applied"
    )  # not_applied | applied | failed | rolled_back
    applied_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Approved field names selected by admin during review
    approved_fields = Column(JSON, nullable=True)

    # Operational telemetry for TEC
    candidates_found = Column(Integer, nullable=False, default=0, server_default="0")
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    http_429_count = Column(Integer, nullable=False, default=0, server_default="0")
    processing_time_ms = Column(Float, nullable=True)
    is_mocked = Column(Boolean, nullable=False, default=False, server_default="false")

    created_at = Column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at = Column(DateTime, nullable=False, default=_utc_now_naive, onupdate=_utc_now_naive)

    __table_args__ = (
        UniqueConstraint("active_lock", name="uq_metadata_enrichment_jobs_active_lock"),
        Index("ix_metadata_enrichment_jobs_movie_status", "movie_id", "status"),
        Index("ix_metadata_enrichment_jobs_created_at", "created_at"),
    )


class MetadataCandidate(Base):
    """Stores a candidate TMDB match and its validated, staged metadata diff."""

    __tablename__ = "metadata_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metadata_enrichment_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(30), nullable=False, default="tmdb", server_default="tmdb")
    provider_movie_id = Column(String(64), nullable=False)
    source_language = Column(String(16), nullable=False, default="en-US", server_default="en-US")

    # Summary identity attributes
    title = Column(String(255), nullable=False)
    original_title = Column(String(255), nullable=True)
    release_date = Column(Date, nullable=True)
    release_year = Column(Integer, nullable=True)
    original_language = Column(String(16), nullable=True)
    director = Column(String(255), nullable=True)

    # Matching diagnostics
    match_score = Column(Float, nullable=False, default=0.0)
    match_status = Column(
        String(40), nullable=False, default="review_required"
    )  # verified_id | review_required | ambiguous | conflict
    is_verified_id_match = Column(Boolean, nullable=False, default=False, server_default="false")
    match_evidence = Column(JSON, nullable=False)
    conflicts = Column(JSON, nullable=False)
    reason_for_review = Column(Text, nullable=True)

    # Staged field-level comparison (normalized, validated, no raw bloat)
    proposed_fields = Column(JSON, nullable=False)
    existing_values = Column(JSON, nullable=False)
    field_conflicts = Column(JSON, nullable=False)

    review_state = Column(
        String(30), nullable=False, default="pending", server_default="pending"
    )  # pending | selected | approved | rejected
    retrieved_at = Column(DateTime, nullable=False, default=_utc_now_naive)

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "provider",
            "provider_movie_id",
            name="uq_metadata_candidates_job_provider_movie",
        ),
        Index("ix_metadata_candidates_job_score", "job_id", "match_score"),
        Index("ix_metadata_candidates_movie_id", "movie_id"),
    )


class MetadataFieldProvenance(Base):
    """Records field-level provenance for every approved metadata update applied to a Movie."""

    __tablename__ = "metadata_field_provenances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metadata_enrichment_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metadata_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_name = Column(String(64), nullable=False)
    provider = Column(String(30), nullable=False, default="tmdb")
    provider_movie_id = Column(String(64), nullable=False)
    source_language = Column(String(16), nullable=False, default="en-US")
    previous_value = Column(JSON, nullable=True)
    applied_value = Column(JSON, nullable=True)
    approved_by_email = Column(String(255), nullable=False)
    retrieved_at = Column(DateTime, nullable=False)
    applied_at = Column(DateTime, nullable=False, default=_utc_now_naive)

    __table_args__ = (
        Index("ix_metadata_field_provenances_movie_field", "movie_id", "field_name"),
        Index("ix_metadata_field_provenances_job_id", "job_id"),
    )


class MetadataReviewEvent(Base):
    """Immutable audit log of administrative review and application decisions."""

    __tablename__ = "metadata_review_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metadata_enrichment_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metadata_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewing_admin_email = Column(String(255), nullable=False)
    action = Column(
        String(40), nullable=False
    )  # select_candidate | approve_fields | reject_job | apply_approved
    review_state_before = Column(String(30), nullable=True)
    review_state_after = Column(String(30), nullable=False)
    approved_fields = Column(JSON, nullable=True)
    rejected_fields = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now_naive)

    __table_args__ = (
        Index("ix_metadata_review_events_job_id", "job_id"),
        Index("ix_metadata_review_events_movie_id", "movie_id"),
    )

