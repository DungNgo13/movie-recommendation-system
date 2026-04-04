import sqlite3

def add_step_column():
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(movies);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'processing_step' not in columns:
            print("Adding processing_step column...")
            cursor.execute("ALTER TABLE movies ADD COLUMN processing_step VARCHAR(100) DEFAULT NULL;")
            conn.commit()
            print("Successfully added processing_step column!")
        else:
            print("processing_step column already exists!")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_step_column()
