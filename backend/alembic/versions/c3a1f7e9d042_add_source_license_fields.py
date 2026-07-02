"""add source and license fields to movies

Revision ID: c3a1f7e9d042
Revises: 87079e588ea0
Create Date: 2026-07-02 12:33:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1f7e9d042'
down_revision: Union[str, None] = '87079e588ea0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add copyright/license tracking columns to the movies table."""
    with op.batch_alter_table("movies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_name", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("source_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("license_type", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("license_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("attribution", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("is_public_domain", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column("media_rights_status", sa.String(30), nullable=False, server_default="unknown")
        )


def downgrade() -> None:
    """Remove copyright/license tracking columns from the movies table."""
    with op.batch_alter_table("movies", schema=None) as batch_op:
        batch_op.drop_column("media_rights_status")
        batch_op.drop_column("is_public_domain")
        batch_op.drop_column("attribution")
        batch_op.drop_column("license_url")
        batch_op.drop_column("license_type")
        batch_op.drop_column("source_url")
        batch_op.drop_column("source_name")
