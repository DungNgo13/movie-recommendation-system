"""add r2 upload sessions and movie source storage

Adds:
  * movies.source_storage     VARCHAR(10)  NOT NULL DEFAULT 'local'
  * movies.source_object_key  VARCHAR(512) NULL
  * upload_sessions table (direct-to-R2 source-video uploads)

Safety notes for reviewers:
  * Purely additive — no existing column is altered or dropped.
  * The server_default 'local' back-fills every existing movie row, so the
    current local-disk upload + FFmpeg/HLS flow is unaffected.
  * Review the generated SQL with ``alembic upgrade head --sql`` before
    applying to PostgreSQL.  Take a database backup first.

Revision ID: f7c3d9a1b2e4
Revises: e5f3a1b2c7d8
Create Date: 2026-10-25 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c3d9a1b2e4'
down_revision: Union[str, None] = 'e5f3a1b2c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add movie source-storage columns and create upload_sessions."""
    op.add_column(
        "movies",
        sa.Column("source_storage", sa.String(10), nullable=False, server_default="local"),
    )
    op.add_column(
        "movies",
        sa.Column("source_object_key", sa.String(512), nullable=True),
    )

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("storage_backend", sa.String(10), nullable=False, server_default="r2"),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("actual_size", sa.BigInteger(), nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("object_key", name="uq_upload_sessions_object_key"),
    )
    op.create_index(
        "ix_upload_sessions_movie_status", "upload_sessions", ["movie_id", "status"]
    )


def downgrade() -> None:
    """Drop upload_sessions and the movie source-storage columns."""
    op.drop_index("ix_upload_sessions_movie_status", table_name="upload_sessions")
    op.drop_table("upload_sessions")
    with op.batch_alter_table("movies") as batch_op:
        batch_op.drop_column("source_object_key")
        batch_op.drop_column("source_storage")
