"""
fix_db.py -- Quick fix for the missing avatar_path column.

Run this once from the backend/ directory:
    python fix_db.py

It will add the avatar_path column to the existing users table.
If the column already exists, it silently skips.
"""

import sys
import os

# Ensure .env is loaded before importing anything
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database import engine


def main():
    print("=== Database Schema Fix ===")
    print(f"Database: {engine.url}")
    print()

    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255)"
            ))
            conn.commit()
            print("[OK] Column 'avatar_path' added to 'users' table.")
    except Exception as exc:
        error_msg = str(exc).lower()
        if "duplicate column" in error_msg or "already exists" in error_msg:
            print("[INFO] Column 'avatar_path' already exists -- no changes needed.")
        else:
            print(f"[ERROR] {exc}")
            sys.exit(1)

    print()
    print("Done! Restart your uvicorn server to pick up the changes.")


if __name__ == "__main__":
    main()
