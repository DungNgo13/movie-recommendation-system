"""
Alembic env.py — configured for the Laetus project.

Key customizations vs. the default template:
  1. Loads .env via dotenv so DATABASE_URL is available.
  2. Sets sqlalchemy.url dynamically from DATABASE_URL (not from alembic.ini).
  3. Imports ALL model modules so autogenerate can detect every table/column.
  4. Points target_metadata at the shared Base.metadata.
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ─── Load .env FIRST ─────────────────────────────────────────────────────────
load_dotenv()

# ─── Alembic Config object ───────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from the environment (never hardcode in alembic.ini)
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", "sqlite:///./test.db"),
)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ─── Import ALL models so Alembic autogenerate can see every table ───────────
# Each import forces SQLAlchemy to register the table with Base.metadata.
from app.database import Base
from app.models import movie          # noqa: F401
from app.models import user           # noqa: F401
from app.models import user_favorite  # noqa: F401
from app.models import watch_history  # noqa: F401
from app.models import rating         # noqa: F401
from app.models import admin_audit_log  # noqa: F401
from app.models import movie_asset      # noqa: F401

target_metadata = Base.metadata


# ─── Offline migrations ──────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


# ─── Online migrations ───────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to the live database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE support
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
