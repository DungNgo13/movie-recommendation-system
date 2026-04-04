import sqlite3

def add_playback_column():
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(watch_history);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'playback_position_seconds' not in columns:
            print("Adding playback_position_seconds column...")
            cursor.execute("ALTER TABLE watch_history ADD COLUMN playback_position_seconds INTEGER DEFAULT 0;")
            conn.commit()
            print("Successfully added playback_position_seconds column!")
        else:
            print("playback_position_seconds column already exists!")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_playback_column()
