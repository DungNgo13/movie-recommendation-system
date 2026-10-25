"""add upload session cleanup tracking

Adds, for the opt-in R2 cleanup job:
  * upload_sessions.object_deleted_at  TIMESTAMP NULL
  * index ix_upload_sessions_status_expires (status, expires_at)

Separate revision because f7c3d9a1b2e4 is already published (commit 5aaa604);
published migrations must not be edited.  Purely additive.

Revision ID: a1e5c7b9d3f2
Revises: f7c3d9a1b2e4
Create Date: 2026-10-25 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e5c7b9d3f2'
down_revision: Union[str, None] = 'f7c3d9a1b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cleanup tracking column and the cleanup query index."""
    op.add_column(
        "upload_sessions",
        sa.Column("object_deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_upload_sessions_status_expires", "upload_sessions", ["status", "expires_at"]
    )


def downgrade() -> None:
    """Drop the cleanup index and column."""
    op.drop_index("ix_upload_sessions_status_expires", table_name="upload_sessions")
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.drop_column("object_deleted_at")
