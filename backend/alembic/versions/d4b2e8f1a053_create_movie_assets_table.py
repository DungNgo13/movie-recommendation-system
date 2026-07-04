"""create movie_assets table

Revision ID: d4b2e8f1a053
Revises: c3a1f7e9d042
Create Date: 2026-07-02 14:13:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4b2e8f1a053'
down_revision: Union[str, None] = 'c3a1f7e9d042'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the movie_assets table for per-asset license tracking."""
    op.create_table(
        "movie_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(30), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("local_path", sa.String(500), nullable=True),
        sa.Column("source_name", sa.String(100), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("license_type", sa.String(100), nullable=True),
        sa.Column("license_url", sa.String(500), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("is_public_domain", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("media_rights_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_movie_assets_movie_type", "movie_assets", ["movie_id", "asset_type"]
    )


def downgrade() -> None:
    """Drop the movie_assets table."""
    op.drop_index("ix_movie_assets_movie_type", table_name="movie_assets")
    op.drop_table("movie_assets")
