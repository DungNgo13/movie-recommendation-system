"""
Pydantic request and response schemas for Phase 8A Movie Metadata Enrichment.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentTriggerRequest(BaseModel):
    """Request payload to start a metadata enrichment job for a movie."""

    source_language: str = Field(default="en-US", max_length=16)
    include_vi_localization: bool = Field(default=True)
    max_candidates: int = Field(default=5, ge=1, le=10)


class CandidateSelectRequest(BaseModel):
    """Request payload for an admin to select a candidate identity for review."""

    candidate_id: UUID
    notes: Optional[str] = Field(default=None, max_length=1000)


class EnrichmentApproveRequest(BaseModel):
    """
    Request payload for an admin to approve selected fields from a candidate
    and optionally apply them immediately.
    """

    candidate_id: UUID
    approved_fields: List[str] = Field(
        ...,
        min_length=1,
        description="Explicit list of field names approved by the administrator.",
    )
    allow_overwrite_existing: bool = Field(
        default=False,
        description="Must be True if any approved field overwrites non-empty existing data.",
    )
    expected_metadata_version: Optional[int] = Field(
        default=None,
        description="Optimistic concurrency check against Movie.metadata_version.",
    )
    apply_immediately: bool = Field(
        default=True,
        description="When True, applies approved fields to PostgreSQL/SQLite in the same workflow.",
    )
    notes: Optional[str] = Field(default=None, max_length=1000)


class EnrichmentRejectRequest(BaseModel):
    """Request payload for an admin to reject a metadata enrichment job or candidate."""

    candidate_id: Optional[UUID] = None
    reason: str = Field(..., min_length=1, max_length=1000)


class ApplyApprovedMetadataRequest(BaseModel):
    """Explicit request to apply an already-approved enrichment job."""

    expected_metadata_version: Optional[int] = None


class MetadataCandidateSchema(BaseModel):
    """Serialized representation of a staged TMDB candidate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    movie_id: UUID
    provider: str
    provider_movie_id: str
    source_language: str
    title: str
    original_title: Optional[str] = None
    release_date: Optional[date] = None
    release_year: Optional[int] = None
    original_language: Optional[str] = None
    director: Optional[str] = None
    match_score: float
    match_status: str
    is_verified_id_match: bool
    match_evidence: Dict[str, Any]
    conflicts: List[str]
    reason_for_review: Optional[str] = None
    proposed_fields: Dict[str, Any]
    existing_values: Dict[str, Any]
    field_conflicts: Dict[str, Any]
    review_state: str
    retrieved_at: datetime


class MetadataReviewEventSchema(BaseModel):
    """Serialized representation of an administrative review event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    movie_id: UUID
    candidate_id: Optional[UUID] = None
    reviewing_admin_email: str
    action: str
    review_state_before: Optional[str] = None
    review_state_after: str
    approved_fields: Optional[List[str]] = None
    rejected_fields: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: datetime


class MetadataFieldProvenanceSchema(BaseModel):
    """Serialized representation of field-level provenance."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie_id: UUID
    job_id: UUID
    candidate_id: Optional[UUID] = None
    field_name: str
    provider: str
    provider_movie_id: str
    source_language: str
    previous_value: Optional[Any] = None
    applied_value: Optional[Any] = None
    approved_by_email: str
    retrieved_at: datetime
    applied_at: datetime


class MetadataEnrichmentJobSchema(BaseModel):
    """Detailed view of a metadata enrichment job including candidates and review events."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie_id: UUID
    provider: str
    source_language: str
    status: str
    selected_candidate_id: Optional[UUID] = None
    review_state: str
    initiated_by_email: Optional[str] = None
    reviewing_admin_email: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    application_status: str
    applied_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    approved_fields: Optional[List[str]] = None
    candidates_found: int
    retry_count: int
    http_429_count: int
    processing_time_ms: Optional[float] = None
    is_mocked: bool = False
    created_at: datetime
    updated_at: datetime

    candidates: List[MetadataCandidateSchema] = Field(default_factory=list)
    review_events: List[MetadataReviewEventSchema] = Field(default_factory=list)
    provenances: List[MetadataFieldProvenanceSchema] = Field(default_factory=list)
    movie_metadata_version: Optional[int] = None

