"""add_cascade_deletes_and_indexes

Revision ID: 87079e588ea0
Revises: 1780d0eefc59
Create Date: 2026-06-23 14:28:45.021177

Changes:
  - Add ondelete="CASCADE" to movie_id and user_id ForeignKeys in:
    ratings, user_favorites, watch_history
  - Add index on user_favorites.movie_id (ix_user_favorites_movie_id)
  - Add index on watch_history.movie_id (ix_watch_history_movie_id)

Notes:
  - On SQLite, foreign keys are not enforced by default, and the batch-mode
    ALTER TABLE approach struggles with unnamed inline FK constraints.
    Therefore, FK CASCADE changes are applied only on PostgreSQL.
  - Indexes are created unconditionally (they work on both engines).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from alembic import context


# revision identifiers, used by Alembic.
revision: str = '87079e588ea0'
down_revision: Union[str, Sequence[str], None] = '1780d0eefc59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    """Return True when migrating against PostgreSQL."""
    return context.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""
    # ── Indexes: safe on both SQLite and PostgreSQL ──────────────────────
    op.create_index('ix_user_favorites_movie_id', 'user_favorites', ['movie_id'], unique=False)
    op.create_index('ix_watch_history_movie_id', 'watch_history', ['movie_id'], unique=False)

    # ── FK CASCADE: PostgreSQL only (SQLite ignores FK rules anyway) ─────
    if _is_postgres():
        # ratings
        op.drop_constraint('ratings_movie_id_fkey', 'ratings', type_='foreignkey')
        op.drop_constraint('ratings_user_id_fkey', 'ratings', type_='foreignkey')
        op.create_foreign_key('ratings_movie_id_fkey', 'ratings', 'movies', ['movie_id'], ['id'], ondelete='CASCADE')
        op.create_foreign_key('ratings_user_id_fkey', 'ratings', 'users', ['user_id'], ['id'], ondelete='CASCADE')

        # user_favorites
        op.drop_constraint('user_favorites_movie_id_fkey', 'user_favorites', type_='foreignkey')
        op.drop_constraint('user_favorites_user_id_fkey', 'user_favorites', type_='foreignkey')
        op.create_foreign_key('user_favorites_movie_id_fkey', 'user_favorites', 'movies', ['movie_id'], ['id'], ondelete='CASCADE')
        op.create_foreign_key('user_favorites_user_id_fkey', 'user_favorites', 'users', ['user_id'], ['id'], ondelete='CASCADE')

        # watch_history
        op.drop_constraint('watch_history_movie_id_fkey', 'watch_history', type_='foreignkey')
        op.drop_constraint('watch_history_user_id_fkey', 'watch_history', type_='foreignkey')
        op.create_foreign_key('watch_history_movie_id_fkey', 'watch_history', 'movies', ['movie_id'], ['id'], ondelete='CASCADE')
        op.create_foreign_key('watch_history_user_id_fkey', 'watch_history', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    if _is_postgres():
        # watch_history
        op.drop_constraint('watch_history_movie_id_fkey', 'watch_history', type_='foreignkey')
        op.drop_constraint('watch_history_user_id_fkey', 'watch_history', type_='foreignkey')
        op.create_foreign_key('watch_history_movie_id_fkey', 'watch_history', 'movies', ['movie_id'], ['id'])
        op.create_foreign_key('watch_history_user_id_fkey', 'watch_history', 'users', ['user_id'], ['id'])

        # user_favorites
        op.drop_constraint('user_favorites_movie_id_fkey', 'user_favorites', type_='foreignkey')
        op.drop_constraint('user_favorites_user_id_fkey', 'user_favorites', type_='foreignkey')
        op.create_foreign_key('user_favorites_movie_id_fkey', 'user_favorites', 'movies', ['movie_id'], ['id'])
        op.create_foreign_key('user_favorites_user_id_fkey', 'user_favorites', 'users', ['user_id'], ['id'])

        # ratings
        op.drop_constraint('ratings_movie_id_fkey', 'ratings', type_='foreignkey')
        op.drop_constraint('ratings_user_id_fkey', 'ratings', type_='foreignkey')
        op.create_foreign_key('ratings_movie_id_fkey', 'ratings', 'movies', ['movie_id'], ['id'])
        op.create_foreign_key('ratings_user_id_fkey', 'ratings', 'users', ['user_id'], ['id'])

    # Indexes: drop unconditionally
    op.drop_index('ix_watch_history_movie_id', table_name='watch_history')
    op.drop_index('ix_user_favorites_movie_id', table_name='user_favorites')
