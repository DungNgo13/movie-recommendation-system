"""
SQLite → PostgreSQL Data Migration Script
==========================================
Copies all data from the local SQLite database to a PostgreSQL database.

Usage:
  1. Set environment variables:
       SQLITE_SOURCE=sqlite:///./test.db       (default)
       DATABASE_URL=postgresql://user:pass@host:5432/laetus_db

  2. Ensure PostgreSQL schema is ready:
       python -m alembic upgrade head

  3. Run this script:
       python scripts/migrate_sqlite_to_pg.py

Design decisions:
  - Uses SQLAlchemy Core (not ORM) for bulk reads/writes — faster and no
    model validation side effects.
  - Inserts use ON CONFLICT DO NOTHING — safe to re-run after a partial failure.
  - Runs all inserts in a single transaction — atomic: all data copies or none.
  - Handles JSON columns: SQLite stores them as TEXT strings; PostgreSQL
    needs native Python lists/dicts.
  - Handles UUID columns: SQLite stores them as CHAR(32) hex; PostgreSQL
    uses native UUID type. Python uuid.UUID() parses both formats.
  - Tables are migrated in dependency order to respect foreign keys.
  - The SQLite database is NEVER modified (read-only).
"""

import json
import os
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, inspect, text

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()

SQLITE_URL = os.getenv("SQLITE_SOURCE", "sqlite:///./test.db")
PG_URL = os.getenv("DATABASE_URL", "")

if not PG_URL or not PG_URL.startswith("postgresql"):
    print("ERROR: DATABASE_URL must be set to a PostgreSQL connection string.")
    print("       Example: postgresql://user:password@localhost:5432/laetus_db")
    sys.exit(1)

if SQLITE_URL.startswith("postgresql"):
    print("ERROR: SQLITE_SOURCE must point to a SQLite database, not PostgreSQL.")
    sys.exit(1)


# ── Table migration order (parents before children) ─────────────────────────
# This order respects foreign key dependencies.
TABLE_ORDER = [
    "users",
    "movies",
    "ratings",
    "user_favorites",
    "watch_history",
    "admin_audit_logs",
]

# Columns that store JSON (lists/dicts) — need parsing from TEXT on SQLite
JSON_COLUMNS = {
    "movies": ["genres", "cast", "keywords"],
}

# Columns that store UUIDs — need parsing from hex strings on SQLite
UUID_COLUMNS = {
    "users":            ["id"],
    "movies":           ["id"],
    "ratings":          ["id", "user_id", "movie_id"],
    "user_favorites":   ["id", "user_id", "movie_id"],
    "watch_history":    ["id", "user_id", "movie_id"],
    "admin_audit_logs": ["id"],
}


def _parse_uuid(value):
    """Parse a UUID from various SQLite storage formats."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _parse_json(value):
    """Parse a JSON string from SQLite TEXT storage into a Python object."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value  # already parsed
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _convert_row(table_name: str, row: dict) -> dict:
    """Convert a single row from SQLite types to PostgreSQL-compatible types."""
    converted = dict(row)

    # Convert UUID columns
    for col in UUID_COLUMNS.get(table_name, []):
        if col in converted:
            converted[col] = _parse_uuid(converted[col])

    # Convert JSON columns
    for col in JSON_COLUMNS.get(table_name, []):
        if col in converted:
            converted[col] = _parse_json(converted[col])

    # Convert boolean columns (SQLite stores as 0/1 integers)
    if table_name == "watch_history" and "is_completed" in converted:
        converted["is_completed"] = bool(converted["is_completed"])

    return converted


def migrate():
    """Execute the full SQLite → PostgreSQL data migration."""
    print("=" * 60)
    print("  SQLite → PostgreSQL Data Migration")
    print("=" * 60)
    print(f"  Source: {SQLITE_URL}")
    print(f"  Target: {PG_URL.split('@')[0].rsplit(':', 1)[0]}@***")  # hide password
    print()

    # ── Connect to both databases ────────────────────────────────────────
    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    pg_engine = create_engine(PG_URL, pool_pre_ping=True)

    # Reflect schemas
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    pg_meta = MetaData()
    pg_meta.reflect(bind=pg_engine)

    # ── Verify PostgreSQL schema exists ──────────────────────────────────
    pg_tables = set(pg_meta.tables.keys())
    missing = [t for t in TABLE_ORDER if t not in pg_tables]
    if missing:
        print(f"ERROR: PostgreSQL is missing tables: {missing}")
        print("       Run 'python -m alembic upgrade head' first.")
        sys.exit(1)

    # ── Count rows in both databases ─────────────────────────────────────
    print("┌─────────────────────┬───────────┬───────────┐")
    print("│ Table               │ SQLite    │ PG Before │")
    print("├─────────────────────┼───────────┼───────────┤")

    sqlite_counts = {}
    pg_counts_before = {}
    with sqlite_engine.connect() as s_conn, pg_engine.connect() as p_conn:
        for table_name in TABLE_ORDER:
            if table_name in sqlite_meta.tables:
                s_count = s_conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
            else:
                s_count = 0

            p_count = p_conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()

            sqlite_counts[table_name] = s_count
            pg_counts_before[table_name] = p_count
            print(f"│ {table_name:<19} │ {s_count:>9} │ {p_count:>9} │")

    print("└─────────────────────┴───────────┴───────────┘")
    print()

    # ── Migrate data ─────────────────────────────────────────────────────
    total_inserted = 0

    with sqlite_engine.connect() as s_conn, pg_engine.begin() as p_conn:
        for table_name in TABLE_ORDER:
            if table_name not in sqlite_meta.tables:
                print(f"  ⏭  {table_name}: not in SQLite, skipping")
                continue

            s_count = sqlite_counts[table_name]
            if s_count == 0:
                print(f"  ⏭  {table_name}: 0 rows in SQLite, skipping")
                continue

            print(f"  📦 {table_name}: migrating {s_count} rows...", end=" ")

            # Read all rows from SQLite
            sqlite_table = sqlite_meta.tables[table_name]
            rows = s_conn.execute(sqlite_table.select()).fetchall()

            # Get column names from the SQLite table
            col_names = [c.name for c in sqlite_table.columns]

            # Convert rows to dicts and fix types
            converted_rows = []
            for row in rows:
                row_dict = dict(zip(col_names, row))
                converted_rows.append(_convert_row(table_name, row_dict))

            # Get the PostgreSQL table object for insert
            pg_table = pg_meta.tables[table_name]

            # Get the primary key column name for ON CONFLICT
            pk_cols = [c.name for c in pg_table.primary_key.columns]

            if pk_cols:
                # Use PostgreSQL ON CONFLICT DO NOTHING for idempotency
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(pg_table).values(converted_rows)
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
                result = p_conn.execute(stmt)
                inserted = result.rowcount
            else:
                # Fallback: plain insert (shouldn't happen with our schema)
                result = p_conn.execute(pg_table.insert(), converted_rows)
                inserted = len(converted_rows)

            total_inserted += inserted
            print(f"✅ {inserted} new rows inserted")

    print()
    print(f"  Total new rows inserted: {total_inserted}")
    print()

    # ── Verify final counts ──────────────────────────────────────────────
    print("┌─────────────────────┬───────────┬───────────┬────────┐")
    print("│ Table               │ SQLite    │ PG After  │ Status │")
    print("├─────────────────────┼───────────┼───────────┼────────┤")

    all_ok = True
    with pg_engine.connect() as p_conn:
        for table_name in TABLE_ORDER:
            s_count = sqlite_counts[table_name]
            p_count = p_conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()

            status = "✅" if p_count >= s_count else "⚠️"
            if p_count < s_count:
                all_ok = False

            print(f"│ {table_name:<19} │ {s_count:>9} │ {p_count:>9} │   {status}   │")

    print("└─────────────────────┴───────────┴───────────┴────────┘")
    print()

    if all_ok:
        print("✅ Migration completed successfully!")
        print("   All PostgreSQL tables have >= the SQLite row counts.")
    else:
        print("⚠️  Some tables have fewer rows in PostgreSQL than SQLite.")
        print("   This may indicate a foreign key violation or data issue.")
        print("   Re-run this script to retry (it is idempotent).")

    print()
    print("Next steps:")
    print("  1. Update .env: DATABASE_URL=postgresql://...")
    print("  2. Restart the backend: uvicorn app.main:app --reload")
    print("  3. Verify login, search, rating, and recommendations work")


if __name__ == "__main__":
    migrate()
