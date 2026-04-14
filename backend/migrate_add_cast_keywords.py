"""
Migration: add `cast` and `keywords` columns to the `movies` table.

Usage (from the backend/ directory):
    python migrate_add_cast_keywords.py

Safe to run multiple times — each column is only added if it doesn't
already exist (idempotent via PRAGMA table_info check).

Both columns are stored as JSON text (SQLite has no native JSON type;
SQLAlchemy's JSON column serialises lists to a JSON string automatically).
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. It will be created fresh by SQLAlchemy on next startup.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(movies)")
        columns = [info[1] for info in cursor.fetchall()]

        # ── cast column ───────────────────────────────────────────────────────
        # Stores a JSON-encoded list of top-billed actor names.
        # Example value: '["Tom Hanks", "Robin Wright"]'
        if "cast" not in columns:
            cursor.execute("ALTER TABLE movies ADD COLUMN cast JSON")
            print("Added 'cast' column to 'movies' table.")
        else:
            print("'cast' column already exists — skipping.")

        # ── keywords column ───────────────────────────────────────────────────
        # Stores a JSON-encoded list of thematic keyword/tag strings.
        # Example value: '["heist", "space", "based on true story"]'
        if "keywords" not in columns:
            cursor.execute("ALTER TABLE movies ADD COLUMN keywords JSON")
            print("Added 'keywords' column to 'movies' table.")
        else:
            print("'keywords' column already exists — skipping.")

        conn.commit()
        print("Migration complete.")

    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
