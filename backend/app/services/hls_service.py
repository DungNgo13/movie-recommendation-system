import os
import subprocess
from uuid import UUID
from datetime import datetime
from ..database import SessionLocal
from ..models import movie as movie_model

def get_hls_output_dir(movie_id: str) -> str:
    folder = os.path.join("uploads", "videos", "hls", str(movie_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def process_hls_conversion(movie_id: UUID):
    """
    Background task to process an uploaded mp4 into an HLS format via FFmpeg.
    """
    db = SessionLocal()
    try:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if not db_movie or not db_movie.video_url:
            return
            
        # Strip API domain logically pointing to local disk buffer
        # Example video_url: http://localhost:8000/uploads/videos/source/123.mp4
        # Becomes generic path: uploads/videos/source/123.mp4
        
        # Native string parsing stripping generic localhost roots natively
        if db_movie.video_url.startswith("http://localhost:8000/"):
            source_path = db_movie.video_url.replace("http://localhost:8000/", "")
        else:
            source_path = db_movie.video_url

        if not os.path.exists(source_path):
            db_movie.video_status = "failed"
            db_movie.processing_error = "Source video file missing from disk."
            db.commit()
            return

        db_movie.video_status = "processing"
        db_movie.processing_error = None
        db.commit()
        
        output_dir = get_hls_output_dir(str(movie_id))
        playlist_path = os.path.join(output_dir, "index.m3u8")

        # Command for converting standard mp4 to HLS safely handling baseline levels
        cmd = [
            "ffmpeg",
            "-y",
            "-i", source_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-f", "hls",
            playlist_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            db_movie.video_status = "failed"
            db_movie.processing_error = f"FFmpeg Error:\n{result.stderr[-500:]}"
            db.commit()
            return
            
        # Successfully generated HLS matrix
        db_movie.video_status = "ready"
        db_movie.hls_playlist_url = f"http://localhost:8000/{output_dir.replace(os.path.sep, '/')}/index.m3u8"
        db_movie.processing_error = None
        db.commit()

    except Exception as e:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if db_movie:
            db_movie.video_status = "failed"
            db_movie.processing_error = str(e)
            db.commit()
    finally:
        db.close()
