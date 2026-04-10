"""
Migration: add duration_seconds and is_completed to watch_history table.
Run once: py migrate_watch_progress.py
"""
import sqlite3

def run():
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(watch_history);")
        cols = {row[1] for row in cursor.fetchall()}

        if 'duration_seconds' not in cols:
            cursor.execute("ALTER TABLE watch_history ADD COLUMN duration_seconds INTEGER DEFAULT 0;")
            print("Added duration_seconds")
        else:
            print("duration_seconds already exists")

        if 'is_completed' not in cols:
            cursor.execute("ALTER TABLE watch_history ADD COLUMN is_completed INTEGER DEFAULT 0;")
            print("Added is_completed")
        else:
            print("is_completed already exists")

        conn.commit()
        print("Migration complete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
