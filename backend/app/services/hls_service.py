import os
import subprocess
import shutil
import logging
from uuid import UUID
from datetime import datetime
from ..database import SessionLocal
from ..models import movie as movie_model

logger = logging.getLogger(__name__)

def process_hls_conversion(movie_id: UUID):
    """
    Background task to process an uploaded mp4 into an HLS format via FFmpeg.
    Strictly follows OS native pathing avoiding URL dependencies explicitly.
    """
    db = SessionLocal()
    db_movie = None
    try:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if not db_movie or not db_movie.video_source_path:
            return
            
        source_path = db_movie.video_source_path

        if not os.path.exists(source_path):
            db_movie.processing_status = "failed"
            db_movie.processing_error = "Source video file missing from disk."
            db.commit()
            return

        db_movie.processing_status = "processing"
        db_movie.processing_error = None
        db.commit()
        
        # New Strict Structure requirement: media/videos/hls/movie_{movie_id}
        output_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        
        if os.path.exists(output_dir) and os.path.isdir(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                db_movie.processing_status = "failed"
                db_movie.processing_error = f"Failed scrubbing previous HLS output natively: {e}"
                db.commit()
                return
            
        os.makedirs(output_dir, exist_ok=True)
        playlist_path = os.path.join(output_dir, "master.m3u8")

        # Command for converting standard mp4 to HLS maintaining exact strict bounds
        cmd = [
            "ffmpeg",
            "-y",
            "-i", source_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-f", "hls",
            "-hls_segment_filename", os.path.join(output_dir, "segment_%03d.ts"),
            playlist_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            db_movie.processing_status = "failed"
            db_movie.processing_error = f"FFmpeg Error:\n{result.stderr[-500:]}"
            db.commit()
            return
            
        db_movie.processing_status = "ready"
        db_movie.hls_playlist_path = os.path.normpath(playlist_path).replace("\\", "/")
        db_movie.processing_error = None
        db.commit()

    except Exception as e:
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_error = str(e)
            db.commit()
    finally:
        db.close()
