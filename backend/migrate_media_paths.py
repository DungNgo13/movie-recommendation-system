import os
import shutil
from sqlalchemy import create_engine
from app.database import SQLALCHEMY_DATABASE_URL

def run_migration():
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        print("This simple script is optimized for SQLite.")
        return

    try:
        # Move existing uploads to media structurally resolving Legacy assets
        if os.path.exists("uploads"):
            print("Migrating physical 'uploads' directory into 'media'...")
            if not os.path.exists("media"):
                shutil.move("uploads", "media")
            else:
                print("'media' folder already exists, assuming manually structured.")
    except Exception as e:
        print(f"Exception moving physical OS directory bounds: {e}")

    from sqlalchemy import text
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        print("Migrating 'movies' Database Table structure...")
        
        # 1. Fetch current column lists natively
        result = conn.execute(text("PRAGMA table_info(movies)"))
        columns = [row[1] for row in result]
        
        # 2. Rename Legacy Columns conditionally resolving crashes cleanly
        renames = {
            "poster_url": "poster_path",
            "backdrop_url": "backdrop_path",
            "video_url": "video_source_path",
            "hls_playlist_url": "hls_playlist_path",
            "video_status": "processing_status"
        }
        
        for old_name, new_name in renames.items():
            if old_name in columns and new_name not in columns:
                print(f"Renaming column {old_name} -> {new_name}")
                conn.execute(text(f"ALTER TABLE movies RENAME COLUMN {old_name} TO {new_name}"))
            elif new_name in columns:
                print(f"Column {new_name} already exists.")
                
        # Fetch updated
        result = conn.execute(text("PRAGMA table_info(movies)"))
        columns_updated = [row[1] for row in result]
        
        # 3. Add original metadata filename natively
        if "video_original_filename" not in columns_updated:
            print("Adding column 'video_original_filename'")
            conn.execute(text("ALTER TABLE movies ADD COLUMN video_original_filename VARCHAR(255)"))
            
        # 4. Mutate strings converting absolutist 'http://localhost:8000/uploads/...' 
        # to normalized relative chunks: 'media/...' inherently natively structurally 
        try:
            print("Purging legacy 'http://localhost:8000/uploads/' URL references...")
            for col in ["poster_path", "backdrop_path", "video_source_path", "hls_playlist_path"]:
                if col in columns_updated or col in renames.values():
                    conn.execute(text(f"UPDATE movies SET {col} = REPLACE({col}, 'http://localhost:8000/uploads/', 'media/') WHERE {col} LIKE 'http://%'"))
            conn.commit()
            print("String normalizations formally completed.")
        except Exception as e:
            print(f"Failed mutating strings natively: {e}")
            
    print("Asset Path Schema Migration entirely finished!")

if __name__ == "__main__":
    run_migration()
