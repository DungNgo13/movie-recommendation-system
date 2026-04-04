import os
import shutil
import logging
from uuid import UUID
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from .movie_service import get_movie
from .file_storage_service import store_file, MEDIA_ROOT

logger = logging.getLogger(__name__)

def upload_image_asset(db: Session, movie_id: UUID, file: UploadFile, image_type: str):
    db_movie = get_movie(db, movie_id)
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    storage_category = f"{image_type}s"
    metadata = store_file(file, str(movie_id), "images", storage_category)
    
    if image_type == "poster":
        db_movie.poster_path = metadata["relative_path"]
    else:
        db_movie.backdrop_path = metadata["relative_path"]
        
    db.commit()
    db.refresh(db_movie)
    return db_movie

def upload_video_asset(db: Session, movie_id: UUID, file: UploadFile):
    db_movie = get_movie(db, movie_id)
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    old_vid_path = db_movie.video_source_path if (db_movie.video_source_path and not db_movie.video_source_path.startswith("http")) else None
    old_hls_folder = os.path.dirname(db_movie.hls_playlist_path) if (db_movie.hls_playlist_path and not db_movie.hls_playlist_path.startswith("http")) else None
    
    # Securely write new file natively before ANY cleanup occurs
    metadata = store_file(file, str(movie_id), "videos", "source")
    
    # Clean old items securely without breaking execution natively
    if old_vid_path and os.path.exists(old_vid_path) and os.path.isfile(old_vid_path):
        try:
            os.remove(old_vid_path)
        except OSError as e:
            logger.warning(f"Failed to cleanly remove stale Source MP4 asset [{old_vid_path}]: {e}")

    if old_hls_folder and os.path.exists(old_hls_folder) and os.path.isdir(old_hls_folder):
        try:
            shutil.rmtree(old_hls_folder)
        except OSError as e:
            logger.warning(f"Failed scrubbing legacy HLS directory [{old_hls_folder}]: {e}")

    db_movie.video_source_path = metadata["relative_path"]
    db_movie.video_original_filename = metadata["original_filename"]
    
    # Strictly reset pipeline constraints generating clean arrays flawlessly naturally
    db_movie.processing_status = "uploaded"
    db_movie.hls_playlist_path = None
    db_movie.processing_error = None
    
    db.commit()
    db.refresh(db_movie)
    return db_movie
