"""
Migration: Add security columns to the 'users' table.

New columns:
  - status              VARCHAR(20)  DEFAULT 'active'
  - last_login_ip       VARCHAR(45)
  - last_login_at       DATETIME
  - last_password_change DATETIME
  - last_email_change   DATETIME
  - failed_login_attempts INTEGER   DEFAULT 0
  - password_reset_token  VARCHAR(64)
  - password_reset_expires DATETIME

Run:  python migrate_add_user_security.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")

COLUMNS = [
    ("status",                  "VARCHAR(20) NOT NULL DEFAULT 'active'"),
    ("last_login_ip",           "VARCHAR(45)"),
    ("last_login_at",           "DATETIME"),
    ("last_password_change",    "DATETIME"),
    ("last_email_change",       "DATETIME"),
    ("failed_login_attempts",   "INTEGER NOT NULL DEFAULT 0"),
    ("password_reset_token",    "VARCHAR(64)"),
    ("password_reset_expires",  "DATETIME"),
]


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. It will be created fresh by SQLAlchemy.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        existing = {info[1] for info in cursor.fetchall()}

        added = 0
        for col_name, col_def in COLUMNS:
            if col_name not in existing:
                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                cursor.execute(sql)
                print(f"  + Added column '{col_name}'")
                added += 1
            else:
                print(f"  ✓ Column '{col_name}' already exists")

        conn.commit()
        print(f"\nMigration complete. {added} column(s) added.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
