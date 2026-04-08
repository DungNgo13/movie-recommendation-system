import os
import subprocess
import shutil
import logging
import re
import threading
from uuid import UUID
from ..database import SessionLocal
from ..models import movie as movie_model

logger = logging.getLogger(__name__)

def get_video_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except (ValueError, TypeError, FileNotFoundError):
        return 0.0

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
        db_movie.processing_step = "Queued"
        db_movie.processing_progress = 0
        db_movie.processing_error = None
        db.commit()
        
        total_duration = get_video_duration(source_path)
        
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

        # Parse conversion arrays natively cleanly explicitly mapping layers safely
        db_movie.processing_step = "Preparing conversion"
        db.commit()
        
        # Multi-quality HLS command: 720p + 360p variants with a master playlist
        # -progress pipe:2 sends progress key=value lines to stderr
        cmd = [
            "ffmpeg",
            "-y",
            "-i", source_path,
            "-filter_complex", "[0:v]split=2[v1][v2]; [v1]scale=w=-2:h=720[v1out]; [v2]scale=w=-2:h=360[v2out]",
            "-map", "[v1out]", "-c:v:0", "libx264", "-b:v:0", "2000k", "-maxrate:v:0", "2140k", "-bufsize:v:0", "4200k",
            "-map", "[v2out]", "-c:v:1", "libx264", "-b:v:1", "800k",  "-maxrate:v:1", "856k",  "-bufsize:v:1", "1200k",
            "-map", "0:a?", "-c:a", "aac", "-b:a", "128k",
            "-f", "hls",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-hls_playlist_type", "vod",
            "-master_pl_name", "master.m3u8",
            "-hls_segment_filename", os.path.join(output_dir, "v%v_segment_%03d.ts"),
            "-var_stream_map", "v:0,a:0 v:1,a:0",
            "-progress", "pipe:2",  # write progress to stderr, not stdout
            os.path.join(output_dir, "v%v_playlist.m3u8")
        ]

        db_movie.processing_step = "Converting to HLS"
        db.commit()

        logger.info("[HLS] Spawning FFmpeg: %s", " ".join(cmd))

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Drain stdout in a background thread to prevent pipe deadlock.
        # (With -progress pipe:2, stdout should be empty for HLS muxer output,
        #  but we drain it anyway to be safe.)
        stdout_lines = []
        def drain_stdout():
            for line in process.stdout:
                stdout_lines.append(line)
        stdout_thread = threading.Thread(target=drain_stdout, daemon=True)
        stdout_thread.start()

        # Read stderr line-by-line for progress + capture errors.
        last_progress = 0
        stderr_lines = []
        for line in process.stderr:
            stderr_lines.append(line)
            match = re.search(r"out_time_us=(\d+)", line)
            if match and total_duration > 0:
                out_time_us = int(match.group(1))
                time_s = out_time_us / 1_000_000.0
                progress_percent = min(int((time_s / total_duration) * 100), 99)
                if progress_percent > last_progress + 1:
                    last_progress = progress_percent
                    db_movie.processing_progress = progress_percent
                    db.commit()

        stdout_thread.join(timeout=10)
        db_movie.processing_step = "Finalizing playlist"
        db.commit()
        process.wait()
        stderr_output = "".join(stderr_lines)

        if process.returncode != 0:
            db.refresh(db_movie)
            if db_movie.processing_status != "processing":
                logger.info("Movie status changed while FFmpeg was running. Skipping failure state overwrite.")
                return
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = f"FFmpeg Error:\n{stderr_output[-500:]}"
            db.commit()
            return
            
        db.refresh(db_movie)
        if db_movie.processing_status != "processing":
            logger.info("Movie status changed while FFmpeg was running. Skipping ready state overwrite.")
            return

        db_movie.processing_status = "ready"
        db_movie.processing_step = "Ready"
        db_movie.processing_progress = 100
        db_movie.hls_playlist_path = os.path.normpath(playlist_path).replace("\\", "/")
        db_movie.processing_error = None
        db.commit()

    except FileNotFoundError:
        # FFmpeg binary is not installed or not on PATH
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = (
                "FFmpeg is not installed or not found on PATH. "
                "Please install FFmpeg and ensure it is accessible from the command line."
            )
            db.commit()
    except Exception as e:
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = str(e)
            db.commit()
    finally:
        db.close()
