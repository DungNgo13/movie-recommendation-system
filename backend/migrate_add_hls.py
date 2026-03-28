import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. It will be created fresh by SQLAlchemy.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(movies)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "hls_playlist_url" not in columns:
            cursor.execute("ALTER TABLE movies ADD COLUMN hls_playlist_url VARCHAR(255)")
            print("Successfully added 'hls_playlist_url' column to 'movies' table.")
        else:
            print("'hls_playlist_url' column already exists in 'movies' table.")

        if "processing_error" not in columns:
            cursor.execute("ALTER TABLE movies ADD COLUMN processing_error TEXT")
            print("Successfully added 'processing_error' column to 'movies' table.")
        else:
            print("'processing_error' column already exists in 'movies' table.")

        conn.commit()
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
