"""
Migration: add available_qualities column to movies table (PostgreSQL).
Run once from the backend/ directory:
  py migrate_available_qualities.py
"""
from app.database import engine
from sqlalchemy import text, inspect

with engine.connect() as conn:
    # Check if the column already exists before altering
    inspector = inspect(engine)
    existing_cols = [c["name"] for c in inspector.get_columns("movies")]

    if "available_qualities" not in existing_cols:
        conn.execute(text(
            "ALTER TABLE movies ADD COLUMN available_qualities VARCHAR(100)"
        ))
        conn.commit()
        print("Migration OK: available_qualities column added.")
    else:
        print("Column available_qualities already exists — nothing to do.")
