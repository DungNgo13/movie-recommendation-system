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

# ---------------------------------------------------------------------------
# Global process registry  { movie_id (str) -> subprocess.Popen }
# ---------------------------------------------------------------------------
active_encodes: dict[str, subprocess.Popen] = {}


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


def get_video_dimensions(path: str) -> tuple[int, int]:
    """
    Return (width, height) of the first video stream via a single ffprobe call.
    Falls back to (0, 0) on any error so callers always get safe integers.

    Using both dimensions avoids misclassifying cinematic videos whose cropped
    height falls just below a round number (e.g. 1280x714 is still 720p HD).
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        # Output is two lines:  line 0 = width, line 1 = height
        parts = result.stdout.strip().splitlines()
        return int(parts[0]), int(parts[1])
    except (ValueError, TypeError, IndexError, FileNotFoundError):
        return 0, 0


# Keep the old single-value helper for any callers outside this file.
def get_video_height(path: str) -> int:
    _, h = get_video_dimensions(path)
    return h


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


def _spawn_ffmpeg(
    cmd: list,
    db,
    db_movie,
    total_duration: float,
    movie_id: str | None = None,
):
    """
    Spawn FFmpeg, drain stdout in a thread, parse progress from stderr.

    If *movie_id* is provided the process is registered in :data:`active_encodes`
    so that :func:`cancel_encode_task` can kill it at any time.

    Returns (returncode, stderr_lines).
    """
    logger.info("[HLS] FFmpeg command:\n  %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Register so the cancel endpoint can reach this process.
    if movie_id is not None:
        active_encodes[str(movie_id)] = process

    # Drain stdout in background thread to prevent pipe deadlock.
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
        # Always deregister regardless of success / failure / kill.
        if movie_id is not None:
            active_encodes.pop(str(movie_id), None)

    return process.returncode, stderr_lines


def _build_multi_quality_cmd(
    src: str, output_dir: str, audio: bool, source_width: int, source_height: int
) -> tuple[list, list[str]]:
    """
    Build a single-pass multi-variant HLS FFmpeg command.

    Tier thresholds use width OR height so cinematic aspect ratios
    (e.g. 1280x714) are not incorrectly downgraded:

      1080p: width >= 1900  OR  height >= 1000
       720p: width >= 1200  OR  height >=  680
       480p: width >=  854  OR  height >=  460
       360p: always included (base quality)

    Audio strategy:
      Use [0:a]asplit=N to create N independent audio outputs (ao0, ao1…).
      Each variant then references its own video (v:i) and audio (a:i)
      stream, avoiding the "Same elementary stream found more than once"
      error that occurs when a single -map 0:a is shared across variants.

    Returns (cmd, quality_labels) so callers know which tiers were built.
    """
    # ── Tier selection (no upscaling) ────────────────────────────────────────
    tiers: list[tuple[str, int, str]] = []   # (filter_label, target_height, bitrate)
    tiers.append(("v360p",  360,  "800k"))                                   # always
    if source_width >= 854  or source_height >= 460:                         # SD+
        tiers.append(("v480p",  480, "1200k"))
    if source_width >= 1200 or source_height >= 680:                         # HD
        tiers.append(("v720p",  720, "2000k"))
    if source_width >= 1900 or source_height >= 1000:                        # Full HD
        tiers.append(("v1080p", 1080, "4000k"))

    quality_labels = [f"{t[1]}p" for t in tiers]
    n = len(tiers)

    # ── filter_complex ────────────────────────────────────────────────────────
    # Video: split once and scale to each target height.
    split_outputs = "".join(f"[s{i}]" for i in range(n))
    filter_parts  = [f"[0:v]split={n}{split_outputs}"]
    for i, (label, height, _) in enumerate(tiers):
        filter_parts.append(f"[s{i}]scale=-2:{height}[{label}]")

    # Audio: asplit into N independent streams so each variant owns one.
    # This prevents "Same elementary stream found more than once" in the
    # HLS muxer which occurs when a single -map 0:a is shared.
    if audio:
        a_outputs = "".join(f"[ao{i}]" for i in range(n))
        if n > 1:
            filter_parts.append(f"[0:a]asplit={n}{a_outputs}")
        else:
            # asplit=1 is not supported by all FFmpeg builds; use anull instead.
            filter_parts.append("[0:a]anull[ao0]")

    filter_complex = "; ".join(filter_parts)

    seg = f"{output_dir}/v%v_segment_%03d.ts"
    out = f"{output_dir}/v%v_playlist.m3u8"

    # ── Maps: video first, then audio ────────────────────────────────────────
    cmd = ["ffmpeg", "-y", "-i", src, "-filter_complex", filter_complex]

    for label, _, _ in tiers:
        cmd += ["-map", f"[{label}]"]          # v:0, v:1, …

    if audio:
        for i in range(n):
            cmd += ["-map", f"[ao{i}]"]        # a:0, a:1, …

    # ── Codec + bitrate specs ────────────────────────────────────────────────
    cmd += ["-c:v", "libx264"]
    for i, (_, _, bitrate) in enumerate(tiers):
        cmd += [f"-b:v:{i}", bitrate]

    if audio:
        cmd += ["-c:a", "aac"]
        for i in range(n):
            cmd += [f"-b:a:{i}", "128k"]

    # ── HLS muxer ────────────────────────────────────────────────────────────
    # Each variant gets its own independent video + audio stream index.
    var_map = " ".join(
        (f"v:{i},a:{i}" if audio else f"v:{i}") for i in range(n)
    )

    cmd += [
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        # -hls_playlist_type vod intentionally omitted: incompatible with var_stream_map
        "-master_pl_name", "master.m3u8",
        "-hls_segment_filename", seg,
        "-var_stream_map", var_map,
        "-progress", "pipe:2",
        out,
    ]
    return cmd, quality_labels



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
        source_width, source_height = get_video_dimensions(source_path)
        logger.info("[HLS] Source: duration=%.1fs, audio=%s, dimensions=%dx%dpx",
                    total_duration, audio, source_width, source_height)

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

        multi_cmd, quality_labels = _build_multi_quality_cmd(
            src_fwd, out_dir_fwd, audio, source_width, source_height
        )
        master_playlist = os.path.join(output_dir, "master.m3u8")

        tier_str = ", ".join(quality_labels)
        db_movie.processing_step = f"Converting to HLS ({tier_str})"
        db.commit()

        rc, stderr_lines = _spawn_ffmpeg(multi_cmd, db, db_movie, total_duration, movie_id=movie_id)

        if rc == 0 and os.path.exists(master_playlist):
            # Multi-quality succeeded
            db.refresh(db_movie)
            if db_movie.processing_status != "processing":
                return
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Ready"
            db_movie.processing_progress = 100
            db_movie.hls_playlist_path = master_playlist.replace("\\", "/")
            db_movie.available_qualities = ",".join(quality_labels)
            db_movie.processing_error = None
            db.commit()
            logger.info("[HLS] Multi-quality conversion complete for movie %s (%s)",
                        movie_id, tier_str)
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
        rc2, stderr_lines2 = _spawn_ffmpeg(fallback_cmd, db, db_movie, total_duration, movie_id=movie_id)

        db.refresh(db_movie)
        if db_movie.processing_status != "processing":
            return

        fallback_pl_path = os.path.join(output_dir, "playlist.m3u8")
        if rc2 == 0 and os.path.exists(fallback_pl_path):
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Ready (480p)"
            db_movie.processing_progress = 100
            db_movie.hls_playlist_path = fallback_pl_path.replace("\\", "/")
            db_movie.available_qualities = "480p"
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
        # Safety net — if we exited abnormally, ensure we're not still registered.
        active_encodes.pop(str(movie_id), None)
        db.close()


# ---------------------------------------------------------------------------
# Cancel / Kill-switch
# ---------------------------------------------------------------------------

def cancel_encode_task(movie_id: UUID) -> dict:
    """
    Kill a running FFmpeg process for *movie_id* and reset DB status to 'ready'.

    Returns a dict with ``cancelled`` (bool) and ``detail`` (str).
    Raises :exc:`KeyError` if no encode is running for that movie.
    """
    mid = str(movie_id)
    process = active_encodes.get(mid)
    if process is None:
        return {"cancelled": False, "detail": "No active encode found for this movie."}

    try:
        process.kill()
    except OSError as exc:
        logger.warning("[HLS] kill() failed for movie %s: %s", mid, exc)

    # Deregister immediately (the _spawn_ffmpeg finally block will be a no-op).
    active_encodes.pop(mid, None)

    # Update DB so the UI reflects the cancelled state.
    db = SessionLocal()
    try:
        db_movie = db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()
        if db_movie:
            db_movie.processing_status = "ready"
            db_movie.processing_step = "Cancelled"
            db_movie.processing_progress = 0
            db_movie.processing_error = "Encode was cancelled by user."
            db.commit()
            logger.info("[HLS] Encode cancelled and DB reset for movie %s", mid)
    except Exception:
        logger.exception("[HLS] DB update failed after cancelling movie %s", mid)
    finally:
        db.close()

    return {"cancelled": True, "detail": "Encode process killed successfully."}
