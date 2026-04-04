import sqlite3

def add_progress_column():
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(movies);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'processing_progress' not in columns:
            print("Adding processing_progress column...")
            cursor.execute("ALTER TABLE movies ADD COLUMN processing_progress INTEGER DEFAULT 0;")
            conn.commit()
            print("Successfully added processing_progress column!")
        else:
            print("processing_progress column already exists!")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_progress_column()
