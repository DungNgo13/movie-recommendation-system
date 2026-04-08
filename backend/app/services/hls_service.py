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


def has_audio_stream(path: str) -> bool:
    """Return True if the source file contains at least one audio stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return bool(result.stdout.strip())
    except Exception:
        return False


def _spawn_ffmpeg(cmd: list, db, db_movie, total_duration: float):
    """
    Spawn FFmpeg, drain stdout in a thread, parse progress from stderr.
    Returns (returncode, stderr_lines).
    """
    logger.info("[HLS] FFmpeg command:\n  %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Drain stdout in background thread to prevent pipe deadlock.
    def drain_stdout():
        for _ in process.stdout:
            pass
    threading.Thread(target=drain_stdout, daemon=True).start()

    last_progress = 0
    stderr_lines: list[str] = []
    for line in process.stderr:
        stderr_lines.append(line)
        m = re.search(r"out_time_us=(\d+)", line)
        if m and total_duration > 0:
            time_s = int(m.group(1)) / 1_000_000.0
            pct = min(int((time_s / total_duration) * 100), 99)
            if pct > last_progress + 1:
                last_progress = pct
                db_movie.processing_progress = pct
                db.commit()

    process.wait()
    return process.returncode, stderr_lines


def _build_multi_quality_cmd(src: str, output_dir: str, audio: bool) -> list:
    """
    Build a 720p + 360p multi-variant HLS command.

    Key correctness rules:
    - ALL -map flags come first, THEN codec specifiers.
    - Use global -c:v / -c:a then per-stream -b:v:N / -b:a:N for bitrates.
    - Do NOT use -hls_playlist_type vod with -var_stream_map (crashes many FFmpeg builds).
    - Forward-slash paths only (required by FFmpeg on Windows for %v/%03d patterns).
    - Conditional audio: only reference a:0 in var_stream_map when audio stream exists.
    """
    seg = f"{output_dir}/v%v_segment_%03d.ts"
    out = f"{output_dir}/v%v_playlist.m3u8"

    # ---- ALL MAPS FIRST ----
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-filter_complex",
        "[0:v]split=2[v720p][v360p]; [v720p]scale=-2:720[v720pout]; [v360p]scale=-2:360[v360pout]",
        "-map", "[v720pout]",   # output video stream 0
        "-map", "[v360pout]",   # output video stream 1
    ]

    if audio:
        cmd += ["-map", "0:a"]  # output audio stream 0

    # ---- CODEC + BITRATE SPECS (after all maps) ----
    cmd += [
        "-c:v", "libx264",
        "-b:v:0", "2000k",      # bitrate for video stream 0 (720p)
        "-b:v:1", "800k",       # bitrate for video stream 1 (360p)
    ]

    if audio:
        cmd += ["-c:a", "aac", "-b:a:0", "128k"]

    # ---- HLS MUXER OPTIONS ----
    var_map = "v:0,a:0 v:1,a:0" if audio else "v:0 v:1"
    cmd += [
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        # NOTE: -hls_playlist_type vod intentionally omitted — incompatible with var_stream_map
        "-master_pl_name", "master.m3u8",
        "-hls_segment_filename", seg,
        "-var_stream_map", var_map,
        "-progress", "pipe:2",
        out,
    ]
    return cmd


def _build_single_quality_cmd(src: str, output_dir: str, audio: bool) -> tuple[list, str]:
    """
    Fallback single-quality (480p) HLS command.
    Returns (cmd, playlist_path).
    """
    seg = f"{output_dir}/segment_%03d.ts"
    playlist = f"{output_dir}/playlist.m3u8"

    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-vf", "scale=-2:480",
        "-c:v", "libx264", "-b:v", "1200k",
    ]

    if audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]

    cmd += [
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-progress", "pipe:2",
        "-hls_segment_filename", seg,
        playlist,
    ]
    return cmd, playlist


def _clean_ffmpeg_error(stderr_lines: list[str]) -> str:
    """
    Extract meaningful error lines from FFmpeg stderr, dropping
    -progress key=value noise (speed=, fps=, out_time=, progress=, etc.).
    """
    noise_keys = {"speed=", "fps=", "frame=", "out_time", "bitrate=",
                  "total_size=", "dup_frames=", "drop_frames=", "progress=",
                  "stream_", "Lsize="}
    real_lines = [
        l for l in stderr_lines
        if not any(l.strip().startswith(k) for k in noise_keys)
    ]
    result = "".join(real_lines).strip()
    # keep last 600 chars so the frontend stays readable
    return result[-600:] if len(result) > 600 else result


def process_hls_conversion(movie_id: UUID):
    """
    Background task: convert an uploaded mp4 to HLS via FFmpeg.
    Attempts multi-quality (720p + 360p) first, falls back to single-quality (480p).
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
            db_movie.processing_step = "Failed"
            db_movie.processing_error = "Source video file missing from disk."
            db.commit()
            return

        db_movie.processing_status = "processing"
        db_movie.processing_step = "Queued"
        db_movie.processing_progress = 0
        db_movie.processing_error = None
        db.commit()

        total_duration = get_video_duration(source_path)
        audio = has_audio_stream(source_path)

        output_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                db_movie.processing_status = "failed"
                db_movie.processing_step = "Failed"
                db_movie.processing_error = f"Could not clear previous HLS output: {e}"
                db.commit()
                return

        os.makedirs(output_dir, exist_ok=True)

        # Always use forward slashes for FFmpeg paths (required on Windows)
        src_fwd = source_path.replace("\\", "/")
        out_dir_fwd = output_dir.replace("\\", "/")

        # ── Attempt 1: multi-quality ────────────────────────────────────────
        db_movie.processing_step = "Preparing conversion"
        db.commit()

        multi_cmd = _build_multi_quality_cmd(src_fwd, out_dir_fwd, audio)
        master_playlist = os.path.join(output_dir, "master.m3u8")

        db_movie.processing_step = "Converting to HLS"
        db.commit()

        rc, stderr_lines = _spawn_ffmpeg(multi_cmd, db, db_movie, total_duration)

        if rc == 0 and os.path.exists(master_playlist):
            # Multi-quality succeeded
            db.refresh(db_movie)
            if db_movie.processing_status != "processing":
                return
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Ready"
            db_movie.processing_progress = 100
            db_movie.hls_playlist_path = master_playlist.replace("\\", "/")
            db_movie.processing_error = None
            db.commit()
            logger.info("[HLS] Multi-quality conversion complete for movie %s", movie_id)
            return

        # ── Attempt 2: single-quality fallback ─────────────────────────────
        logger.warning(
            "[HLS] Multi-quality attempt failed (rc=%d, playlist_exists=%s). "
            "Falling back to single-quality for movie %s",
            rc, os.path.exists(master_playlist), movie_id
        )

        # Clean up partial output so the fallback starts fresh
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        db_movie.processing_step = "Converting to HLS (480p)"
        db_movie.processing_progress = 0
        db.commit()

        fallback_cmd, fallback_playlist = _build_single_quality_cmd(src_fwd, out_dir_fwd, audio)
        rc2, stderr_lines2 = _spawn_ffmpeg(fallback_cmd, db, db_movie, total_duration)

        db.refresh(db_movie)
        if db_movie.processing_status != "processing":
            return

        fallback_pl_path = os.path.join(output_dir, "playlist.m3u8")
        if rc2 == 0 and os.path.exists(fallback_pl_path):
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Ready (480p)"
            db_movie.processing_progress = 100
            db_movie.hls_playlist_path = fallback_pl_path.replace("\\", "/")
            db_movie.processing_error = None
            db.commit()
            logger.info("[HLS] Single-quality fallback complete for movie %s", movie_id)
        else:
            # Both attempts failed
            error_msg = _clean_ffmpeg_error(stderr_lines2 or stderr_lines)
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = error_msg or "FFmpeg conversion failed."
            db.commit()
            logger.error(
                "[HLS] All conversion attempts failed for movie %s (rc=%d)", movie_id, rc2
            )

    except FileNotFoundError:
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = (
                "FFmpeg is not installed or not found on PATH."
            )
            db.commit()
    except Exception as e:
        logger.exception("[HLS] Unexpected error for movie %s", movie_id)
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = str(e)
            db.commit()
    finally:
        db.close()
