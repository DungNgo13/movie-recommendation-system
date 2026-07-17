"""add vietnamese display metadata

Revision ID: e5f3a1b2c7d8
Revises: d4b2e8f1a053
Create Date: 2026-07-17 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f3a1b2c7d8'
down_revision: Union[str, None] = 'd4b2e8f1a053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('movies', sa.Column('title_vi', sa.String(255), nullable=True))
    op.add_column('movies', sa.Column('overview_vi', sa.Text(), nullable=True))
    op.add_column('movies', sa.Column('keyword_labels_vi', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('movies', 'keyword_labels_vi')
    op.drop_column('movies', 'overview_vi')
    op.drop_column('movies', 'title_vi')
