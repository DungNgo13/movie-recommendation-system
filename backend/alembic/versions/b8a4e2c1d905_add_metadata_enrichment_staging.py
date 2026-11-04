"""add metadata enrichment staging and provenance tables

Adds:
  * movies.tmdb_id            INTEGER NULL UNIQUE
  * movies.imdb_id            VARCHAR(20) NULL
  * movies.original_title     VARCHAR(255) NULL
  * movies.original_language  VARCHAR(16) NULL
  * movies.metadata_version   INTEGER NOT NULL DEFAULT 1
  * metadata_enrichment_jobs table
  * metadata_candidates table
  * metadata_field_provenances table
  * metadata_review_events table

Safety notes for reviewers:
  * Purely additive — no existing column or table is altered or dropped.
  * Compatible with both PostgreSQL and SQLite (batch mode).

Revision ID: b8a4e2c1d905
Revises: a1e5c7b9d3f2
Create Date: 2026-11-04 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8a4e2c1d905"
down_revision: Union[str, None] = "a1e5c7b9d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 8A movie external-ID columns and metadata enrichment tables."""
    op.add_column("movies", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("imdb_id", sa.String(20), nullable=True))
    op.add_column("movies", sa.Column("original_title", sa.String(255), nullable=True))
    op.add_column("movies", sa.Column("original_language", sa.String(16), nullable=True))
    op.add_column(
        "movies",
        sa.Column("metadata_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)
    op.create_index("ix_movies_imdb_id", "movies", ["imdb_id"], unique=False)

    op.create_table(
        "metadata_enrichment_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="tmdb"),
        sa.Column("source_language", sa.String(16), nullable=False, server_default="en-US"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("active_lock", sa.String(100), nullable=True),
        sa.Column("selected_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("review_state", sa.String(30), nullable=False, server_default="pending_review"),
        sa.Column("initiated_by_email", sa.String(255), nullable=True),
        sa.Column("reviewing_admin_email", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("application_status", sa.String(30), nullable=False, server_default="not_applied"),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("approved_fields", sa.JSON(), nullable=True),
        sa.Column("candidates_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("http_429_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_time_ms", sa.Float(), nullable=True),
        sa.Column("is_mocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("active_lock", name="uq_metadata_enrichment_jobs_active_lock"),
    )
    op.create_index(
        "ix_metadata_enrichment_jobs_movie_status",
        "metadata_enrichment_jobs",
        ["movie_id", "status"],
    )
    op.create_index(
        "ix_metadata_enrichment_jobs_created_at",
        "metadata_enrichment_jobs",
        ["created_at"],
    )

    op.create_table(
        "metadata_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="tmdb"),
        sa.Column("provider_movie_id", sa.String(64), nullable=False),
        sa.Column("source_language", sa.String(16), nullable=False, server_default="en-US"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_title", sa.String(255), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("original_language", sa.String(16), nullable=True),
        sa.Column("director", sa.String(255), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("match_status", sa.String(40), nullable=False, server_default="review_required"),
        sa.Column("is_verified_id_match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("match_evidence", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("reason_for_review", sa.Text(), nullable=True),
        sa.Column("proposed_fields", sa.JSON(), nullable=False),
        sa.Column("existing_values", sa.JSON(), nullable=False),
        sa.Column("field_conflicts", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["metadata_enrichment_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "job_id",
            "provider",
            "provider_movie_id",
            name="uq_metadata_candidates_job_provider_movie",
        ),
    )
    op.create_index(
        "ix_metadata_candidates_job_score",
        "metadata_candidates",
        ["job_id", "match_score"],
    )
    op.create_index(
        "ix_metadata_candidates_movie_id",
        "metadata_candidates",
        ["movie_id"],
    )

    op.create_table(
        "metadata_field_provenances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_movie_id", sa.String(64), nullable=False),
        sa.Column("source_language", sa.String(16), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("applied_value", sa.JSON(), nullable=True),
        sa.Column("approved_by_email", sa.String(255), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["metadata_enrichment_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["metadata_candidates.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_metadata_field_provenances_movie_field",
        "metadata_field_provenances",
        ["movie_id", "field_name"],
    )
    op.create_index(
        "ix_metadata_field_provenances_job_id",
        "metadata_field_provenances",
        ["job_id"],
    )

    op.create_table(
        "metadata_review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("reviewing_admin_email", sa.String(255), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("review_state_before", sa.String(30), nullable=True),
        sa.Column("review_state_after", sa.String(30), nullable=False),
        sa.Column("approved_fields", sa.JSON(), nullable=True),
        sa.Column("rejected_fields", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["metadata_enrichment_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["metadata_candidates.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_metadata_review_events_job_id",
        "metadata_review_events",
        ["job_id"],
    )
    op.create_index(
        "ix_metadata_review_events_movie_id",
        "metadata_review_events",
        ["movie_id"],
    )


def downgrade() -> None:
    """Drop Phase 8A metadata enrichment tables and columns."""
    op.drop_index("ix_metadata_review_events_movie_id", table_name="metadata_review_events")
    op.drop_index("ix_metadata_review_events_job_id", table_name="metadata_review_events")
    op.drop_table("metadata_review_events")

    op.drop_index("ix_metadata_field_provenances_job_id", table_name="metadata_field_provenances")
    op.drop_index("ix_metadata_field_provenances_movie_field", table_name="metadata_field_provenances")
    op.drop_table("metadata_field_provenances")

    op.drop_index("ix_metadata_candidates_movie_id", table_name="metadata_candidates")
    op.drop_index("ix_metadata_candidates_job_score", table_name="metadata_candidates")
    op.drop_table("metadata_candidates")

    op.drop_index("ix_metadata_enrichment_jobs_created_at", table_name="metadata_enrichment_jobs")
    op.drop_index("ix_metadata_enrichment_jobs_movie_status", table_name="metadata_enrichment_jobs")
    op.drop_table("metadata_enrichment_jobs")

    op.drop_index("ix_movies_imdb_id", table_name="movies")
    op.drop_index("ix_movies_tmdb_id", table_name="movies")
    with op.batch_alter_table("movies") as batch_op:
        batch_op.drop_column("metadata_version")
        batch_op.drop_column("original_language")
        batch_op.drop_column("original_title")
        batch_op.drop_column("imdb_id")
        batch_op.drop_column("tmdb_id")
