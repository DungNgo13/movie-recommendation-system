import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")

def migrate():
    # If using in-memory or alternative db path locally, adapt accordingly
    # main.py runs SQLalchemy engine which maps to sqlite:///./movies.db by default
    
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. It will be created fresh by SQLAlchemy.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if 'role' column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "role" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'")
            conn.commit()
            print("Successfully added 'role' column to 'users' table.")
        else:
            print("'role' column already exists in 'users' table.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
