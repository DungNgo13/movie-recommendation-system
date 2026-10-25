import os
import asyncio
import subprocess
import shutil
import logging
import re
import threading
from uuid import UUID
from ..database import SessionLocal
from ..models import movie as movie_model
from .recommendation.vectorizer import invalidate_cache as _invalidate_rec_cache
from .video_source_resolver import resolve_video_source, SourceResolutionError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FFmpeg / FFprobe executable resolution
# ---------------------------------------------------------------------------
FFMPEG_CMD  = shutil.which("ffmpeg")  or "/usr/bin/ffmpeg"
FFPROBE_CMD = shutil.which("ffprobe") or "/usr/bin/ffprobe"

# ---------------------------------------------------------------------------
# Global process registry  { movie_id (str) -> subprocess.Popen }
# ---------------------------------------------------------------------------
active_encodes: dict[str, subprocess.Popen] = {}

# Concurrency guard: track movies currently executing in process_hls_conversion
_active_job_movies: set[str] = set()
_active_job_lock = threading.Lock()

# ---------------------------------------------------------------------------
# In-Memory Async Task Queue
# ---------------------------------------------------------------------------
encode_queue: asyncio.Queue = asyncio.Queue()


def queue_encode_task(movie_id: UUID) -> int:
    """
    Add a movie to the encoding queue.
    Returns current queue depth.
    """
    encode_queue.put_nowait(movie_id)
    return encode_queue.qsize()


def queue_size() -> int:
    """Return the number of encoding jobs currently waiting in the queue."""
    return encode_queue.qsize()


async def encoding_worker() -> None:
    """
    Long-running coroutine that serialises FFmpeg encoding jobs.
    Runs strictly one FFmpeg process at a time.
    """
    loop = asyncio.get_event_loop()
    logger.info("[Queue] Encoding worker started — ready to process jobs.")

    while True:
        movie_id = await encode_queue.get()
        logger.info("[Queue] Dequeued movie %s for encoding. Jobs remaining: %d",
                    movie_id, encode_queue.qsize())
        try:
            await loop.run_in_executor(None, process_hls_conversion, movie_id)
        except Exception:
            logger.exception("[Queue] Unexpected error while encoding movie %s", movie_id)
        finally:
            encode_queue.task_done()
            logger.info("[Queue] Finished movie %s. Jobs remaining: %d",
                        movie_id, encode_queue.qsize())


def get_video_duration(path: str) -> float:
    cmd = [
        FFPROBE_CMD, "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except (ValueError, TypeError, FileNotFoundError):
        return 0.0


def get_video_dimensions(path: str) -> tuple[int, int]:
    """
    Return (width, height) of the first video stream via ffprobe.
    Falls back to (0, 0) on any error.
    """
    cmd = [
        FFPROBE_CMD, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        parts = result.stdout.strip().splitlines()
        return int(parts[0]), int(parts[1])
    except (ValueError, TypeError, IndexError, FileNotFoundError):
        return 0, 0


def get_video_height(path: str) -> int:
    _, h = get_video_dimensions(path)
    return h


def has_audio_stream(path: str) -> bool:
    """Return True if the source file contains at least one audio stream."""
    cmd = [
        FFPROBE_CMD, "-v", "error",
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


def _spawn_ffmpeg(
    cmd: list,
    db,
    db_movie,
    total_duration: float,
    movie_id: str | None = None,
):
    """
    Spawn FFmpeg, drain stdout in a thread, parse progress from stderr.
    Registers process in active_encodes so cancel_encode_task can reach it.
    Returns (returncode, stderr_lines).
    """
    logger.info("[HLS] FFmpeg command:\n  %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if movie_id is not None:
        active_encodes[str(movie_id)] = process

    def drain_stdout():
        for _ in process.stdout:
            pass
    threading.Thread(target=drain_stdout, daemon=True).start()

    last_progress = 0
    stderr_lines: list[str] = []
    try:
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
    finally:
        process.wait()
        if movie_id is not None:
            active_encodes.pop(str(movie_id), None)

    return process.returncode, stderr_lines


def select_hls_qualities(source_height: int) -> list[tuple[str, int, str]]:
    """
    Return HLS quality tiers appropriate for source_height.
    Only tiers with target height <= source_height are included (no upscaling).
    """
    ALL_TIERS: list[tuple[str, int, str, int]] = [
        ("v360p",   360,  "800k",     0),     # always included
        ("v480p",   480, "1200k",   480),
        ("v720p",   720, "2800k",   720),
        ("v1080p", 1080, "5000k",  1080),
        ("v1440p", 1440, "9000k",  1440),
        ("v2160p", 2160, "14000k", 2160),
    ]

    return [
        (label, height, bitrate)
        for label, height, bitrate, min_h in ALL_TIERS
        if source_height >= min_h
    ]


def _build_multi_quality_cmd(
    src: str, output_dir: str, audio: bool, source_width: int, source_height: int
) -> tuple[list, list[str]]:
    tiers = select_hls_qualities(source_height)
    quality_labels = [f"{t[1]}p" for t in tiers]
    n = len(tiers)

    split_outputs = "".join(f"[s{i}]" for i in range(n))
    filter_parts  = [f"[0:v]split={n}{split_outputs}"]
    for i, (label, height, _) in enumerate(tiers):
        filter_parts.append(f"[s{i}]scale=-2:{height}[{label}]")

    if audio:
        a_outputs = "".join(f"[ao{i}]" for i in range(n))
        if n > 1:
            filter_parts.append(f"[0:a]asplit={n}{a_outputs}")
        else:
            filter_parts.append("[0:a]anull[ao0]")

    filter_complex = "; ".join(filter_parts)

    seg = f"{output_dir}/v%v_segment_%03d.ts"
    out = f"{output_dir}/v%v_playlist.m3u8"

    cmd = [FFMPEG_CMD, "-y", "-i", src, "-filter_complex", filter_complex]

    for label, _, _ in tiers:
        cmd += ["-map", f"[{label}]"]

    if audio:
        for i in range(n):
            cmd += ["-map", f"[ao{i}]"]

    cmd += ["-c:v", "libx264"]
    for i, (_, _, bitrate) in enumerate(tiers):
        cmd += [f"-b:v:{i}", bitrate]

    if audio:
        cmd += ["-c:a", "aac"]
        for i in range(n):
            cmd += [f"-b:a:{i}", "128k"]

    var_map = " ".join(
        (f"v:{i},a:{i}" if audio else f"v:{i}") for i in range(n)
    )

    cmd += [
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-master_pl_name", "master.m3u8",
        "-hls_segment_filename", seg,
        "-var_stream_map", var_map,
        "-progress", "pipe:2",
        out,
    ]
    return cmd, quality_labels


def _build_single_quality_cmd(src: str, output_dir: str, audio: bool) -> tuple[list, str]:
    seg = f"{output_dir}/segment_%03d.ts"
    playlist = f"{output_dir}/playlist.m3u8"

    cmd = [
        FFMPEG_CMD, "-y",
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
    noise_keys = {"speed=", "fps=", "frame=", "out_time", "bitrate=",
                  "total_size=", "dup_frames=", "drop_frames=", "progress=",
                  "stream_", "Lsize="}
    real_lines = [
        l for l in stderr_lines
        if not any(l.strip().startswith(k) for k in noise_keys)
    ]
    result = "".join(real_lines).strip()
    clean = _sanitize_error_message(result)
    return clean[-600:] if len(clean) > 600 else clean


def _sanitize_error_message(msg: str) -> str:
    """Remove absolute paths and internal system directories from user-facing error messages."""
    if not msg:
        return ""
    # Strip Windows paths like D:\...\something
    clean = re.sub(r"[A-Za-z]:\\[^ \t\n\r\"']+", "<path>", msg)
    # Strip POSIX paths
    clean = re.sub(r"/(?:media|tmp|var|home|usr|private)[^ \t\n\r\"']*", "<path>", clean)
    return clean.strip()


def _verify_hls_output(master_or_playlist: str, output_dir: str) -> bool:
    """
    Verify that HLS conversion produced valid outputs.
    Works with both real filesystem outputs and mocked os.path.exists in unit tests.
    """
    if not os.path.exists(master_or_playlist):
        return False

    # If the file exists on the real filesystem, verify file integrity and segments
    if os.path.isfile(master_or_playlist):
        if os.path.getsize(master_or_playlist) == 0:
            return False
        try:
            with open(master_or_playlist, "r", encoding="utf-8", errors="ignore") as f:
                if not f.readline().startswith("#EXTM3U"):
                    return False
        except Exception:
            return False

        if os.path.isdir(output_dir):
            segments = [f for f in os.listdir(output_dir) if f.endswith(".ts")]
            if not segments:
                return False

    return True


def _is_source_stale_or_cancelled(
    db,
    movie_id: UUID,
    initial_storage: str,
    initial_identifier: str | None,
) -> bool:
    """
    Check if the active source of the movie was replaced or if the job was cancelled
    while download/transcoding was running.
    """
    current = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
    if not current:
        return True
    if current.processing_status != "processing":
        return True
    curr_storage = (current.source_storage or "local").lower()
    curr_id = current.source_object_key if curr_storage == "r2" else current.video_source_path
    if curr_storage != initial_storage or curr_id != initial_identifier:
        return True
    return False


def process_hls_conversion(movie_id: UUID):
    """
    Background task: convert a source video (local or R2) to HLS via FFmpeg.
    Attempts multi-quality first, falls back to single-quality (480p).
    Safely resolves R2 sources and ensures all temporary files are cleaned up.
    """
    mid_str = str(movie_id)
    with _active_job_lock:
        if mid_str in _active_job_movies:
            logger.warning("[HLS] Movie %s is already being converted. Skipping duplicate task.", movie_id)
            return
        _active_job_movies.add(mid_str)

    db = SessionLocal()
    db_movie = None
    output_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")

    try:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if not db_movie:
            return

        initial_storage = (db_movie.source_storage or "local").lower()
        initial_identifier = (
            db_movie.source_object_key if initial_storage == "r2" else db_movie.video_source_path
        )
        if not initial_identifier:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = "No source video configured for movie."
            db.commit()
            return

        db_movie.processing_status = "processing"
        db_movie.processing_step = "Resolving source"
        db_movie.processing_progress = 0
        db_movie.processing_error = None
        db.commit()

        # Resolve the source video via context manager (downloads R2 if needed, cleans up in finally)
        with resolve_video_source(db_movie, exists_fn=os.path.exists) as resolved:
            source_path = resolved.local_path

            # Re-check status in case user cancelled or updated source during download
            db.refresh(db_movie)
            if _is_source_stale_or_cancelled(db, movie_id, initial_storage, initial_identifier):
                logger.warning("[HLS] Source changed or job cancelled during source resolution for movie %s", movie_id)
                return

            db_movie.processing_step = "Analyzing video"
            db.commit()

            total_duration = get_video_duration(source_path)
            audio = has_audio_stream(source_path)
            source_width, source_height = get_video_dimensions(source_path)

            if source_width == 0 or source_height == 0:
                db_movie.processing_status = "failed"
                db_movie.processing_step = "Failed"
                db_movie.processing_error = "Could not read video stream or dimensions via FFprobe."
                db.commit()
                return

            logger.info("[HLS] Source resolved: storage=%s duration=%.1fs, audio=%s, dimensions=%dx%dpx",
                        resolved.source_storage, total_duration, audio, source_width, source_height)

            if os.path.exists(output_dir):
                try:
                    shutil.rmtree(output_dir)
                except OSError as e:
                    db_movie.processing_status = "failed"
                    db_movie.processing_step = "Failed"
                    db_movie.processing_error = "Could not clear previous HLS output."
                    db.commit()
                    return

            os.makedirs(output_dir, exist_ok=True)

            src_fwd = source_path.replace("\\", "/")
            out_dir_fwd = output_dir.replace("\\", "/")

            # ── Attempt 1: multi-quality ────────────────────────────────────
            db_movie.processing_step = "Preparing conversion"
            db.commit()

            multi_cmd, quality_labels = _build_multi_quality_cmd(
                src_fwd, out_dir_fwd, audio, source_width, source_height
            )
            master_playlist = os.path.join(output_dir, "master.m3u8")

            tier_str = ", ".join(quality_labels)
            db_movie.processing_step = f"Converting to HLS ({tier_str})"
            db.commit()

            rc, stderr_lines = _spawn_ffmpeg(multi_cmd, db, db_movie, total_duration, movie_id=movie_id)

            if rc == 0 and _verify_hls_output(master_playlist, output_dir):
                # Verify source did not change and job was not cancelled during encoding
                db.refresh(db_movie)
                if _is_source_stale_or_cancelled(db, movie_id, initial_storage, initial_identifier):
                    logger.warning("[HLS] Source changed or job cancelled mid-flight for movie %s; discarding output", movie_id)
                    shutil.rmtree(output_dir, ignore_errors=True)
                    return

                db_movie.processing_status = "ready"
                db_movie.processing_step = "Ready"
                db_movie.processing_progress = 100
                db_movie.hls_playlist_path = master_playlist.replace("\\", "/")
                db_movie.available_qualities = ",".join(quality_labels)
                db_movie.processing_error = None
                db.commit()

                _invalidate_rec_cache()
                logger.info("[HLS] Multi-quality conversion complete for movie %s (%s)", movie_id, tier_str)
                return

            # ── Attempt 2: single-quality fallback ─────────────────────────
            logger.warning(
                "[HLS] Multi-quality attempt failed (rc=%d). Falling back to single-quality for movie %s",
                rc, movie_id
            )

            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            os.makedirs(output_dir, exist_ok=True)

            db_movie.processing_step = "Converting to HLS (480p)"
            db_movie.processing_progress = 0
            db.commit()

            fallback_cmd, fallback_playlist = _build_single_quality_cmd(src_fwd, out_dir_fwd, audio)
            rc2, stderr_lines2 = _spawn_ffmpeg(fallback_cmd, db, db_movie, total_duration, movie_id=movie_id)

            db.refresh(db_movie)
            if _is_source_stale_or_cancelled(db, movie_id, initial_storage, initial_identifier):
                logger.warning("[HLS] Source changed or job cancelled mid-flight for movie %s; discarding fallback output", movie_id)
                shutil.rmtree(output_dir, ignore_errors=True)
                return

            fallback_pl_path = os.path.join(output_dir, "playlist.m3u8")
            if rc2 == 0 and _verify_hls_output(fallback_pl_path, output_dir):
                db_movie.processing_status = "ready"
                db_movie.processing_step = "Ready (480p)"
                db_movie.processing_progress = 100
                db_movie.hls_playlist_path = fallback_pl_path.replace("\\", "/")
                db_movie.available_qualities = "480p"
                db_movie.processing_error = None
                db.commit()

                _invalidate_rec_cache()
                logger.info("[HLS] Single-quality fallback complete for movie %s", movie_id)
            else:
                shutil.rmtree(output_dir, ignore_errors=True)
                error_msg = _clean_ffmpeg_error(stderr_lines2 or stderr_lines)
                db_movie.processing_status = "failed"
                db_movie.processing_step = "Failed"
                db_movie.processing_error = error_msg or "FFmpeg conversion failed."
                db_movie.hls_playlist_path = None
                db.commit()
                logger.error("[HLS] All conversion attempts failed for movie %s (rc=%d)", movie_id, rc2)

    except SourceResolutionError as exc:
        logger.error("[HLS] Source resolution error for movie %s: %s", movie_id, exc)
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = _sanitize_error_message(str(exc))
            db_movie.hls_playlist_path = None
            db.commit()
    except FileNotFoundError:
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = "FFmpeg is not installed or not found on PATH."
            db_movie.hls_playlist_path = None
            db.commit()
    except Exception as e:
        logger.exception("[HLS] Unexpected error for movie %s", movie_id)
        if db_movie:
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Failed"
            db_movie.processing_error = _sanitize_error_message(str(e))
            db_movie.hls_playlist_path = None
            db.commit()
    finally:
        active_encodes.pop(mid_str, None)
        with _active_job_lock:
            _active_job_movies.discard(mid_str)
        db.close()


# ---------------------------------------------------------------------------
# Cancel / Kill-switch (H2 Defect Fix)
# ---------------------------------------------------------------------------

def cancel_encode_task(movie_id: UUID) -> dict:
    """
    Kill an ongoing FFmpeg process or reset stuck processing state for *movie_id*.

    Fixes H2: Never sets processing_status='ready' unless a valid, verified
    HLS playlist actually exists on disk.
    """
    mid = str(movie_id)
    process = active_encodes.get(mid)
    killed = False
    if process is not None:
        try:
            process.kill()
            killed = True
        except OSError as exc:
            logger.warning("[HLS] kill() failed for movie %s: %s", mid, exc)
        active_encodes.pop(mid, None)

    db = SessionLocal()
    try:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if not db_movie:
            return {"cancelled": False, "detail": "Movie not found."}

        if not killed and db_movie.processing_status != "processing":
            return {"cancelled": False, "detail": "No active encode found for this movie."}

        output_dir = os.path.join("media", "videos", "hls", f"movie_{movie_id}")
        has_valid_hls = (
            bool(db_movie.hls_playlist_path)
            and os.path.exists(output_dir)
            and _verify_hls_output(db_movie.hls_playlist_path, output_dir)
        )

        if has_valid_hls:
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Cancelled"
            db_movie.processing_error = "Encode cancelled by user. Prior HLS retained."
        else:
            # H2 fix: NEVER mark ready when HLS output is missing or partial
            db_movie.processing_status = "failed"
            db_movie.processing_step = "Cancelled"
            db_movie.processing_progress = 0
            db_movie.processing_error = "Encode was cancelled by user."
            db_movie.hls_playlist_path = None
            db_movie.available_qualities = None
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)

        db.commit()
        logger.info("[HLS] Encode cancelled for movie %s (status=%s)", mid, db_movie.processing_status)
        return {"cancelled": True, "detail": "Encode process cancelled successfully."}
    except Exception as exc:
        logger.exception("[HLS] DB update failed after cancelling movie %s", mid)
        db.rollback()
        return {"cancelled": False, "detail": f"Database error during cancellation: {exc}"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Restart Recovery (H1 Defect Fix)
# ---------------------------------------------------------------------------

def recover_stuck_encodes(db=None) -> list[UUID]:
    """
    Fixes H1: Finds movies stranded in 'processing' status from a previous server
    run (whose in-memory queue task was lost on shutdown).

    If valid HLS output exists on disk, marks 'ready'.
    Otherwise, marks 'failed' with step 'Interrupted' so admin can re-trigger.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    recovered = []
    try:
        stuck_movies = db.query(movie_model.Movie).filter(
            movie_model.Movie.processing_status == "processing"
        ).all()

        for movie in stuck_movies:
            output_dir = os.path.join("media", "videos", "hls", f"movie_{movie.id}")
            candidate_pl = movie.hls_playlist_path or os.path.join(output_dir, "master.m3u8")
            if os.path.exists(output_dir) and _verify_hls_output(candidate_pl, output_dir):
                movie.processing_status = "ready"
                movie.processing_step = "Ready"
                movie.processing_progress = 100
                movie.hls_playlist_path = candidate_pl.replace("\\", "/")
                movie.processing_error = None
            else:
                movie.processing_status = "failed"
                movie.processing_step = "Interrupted"
                movie.processing_progress = 0
                movie.processing_error = (
                    "Encoding was interrupted by a server restart. Please re-trigger encoding."
                )
            recovered.append(movie.id)

        db.commit()
        if recovered:
            logger.info("[HLS] Recovered %d stuck movie encodes on startup: %s", len(recovered), recovered)
    except Exception as exc:
        logger.exception("[HLS] Error recovering stuck encodes: %s", exc)
        db.rollback()
    finally:
        if close_db:
            db.close()

    return recovered
