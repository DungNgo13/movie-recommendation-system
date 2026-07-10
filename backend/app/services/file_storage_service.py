import os
import shutil
import logging
from datetime import datetime
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

MEDIA_ROOT = "media"

# ─── Upload size limits ──────────────────────────────────────────────────────
MAX_IMAGE_BYTES = 10 * 1024 * 1024          # 10 MB  (poster, backdrop)
MAX_VIDEO_BYTES = 5 * 1024 * 1024 * 1024    # 5 GB

CONTENT_TYPE_EXT_MAP = {
    "image/jpeg":       "jpg",
    "image/png":        "png",
    "image/webp":       "webp",
    # Video containers — extension falls back to original filename if not listed
    "video/mp4":        "mp4",
    "video/x-matroska": "mkv",
    "video/webm":       "webm",
    "video/avi":        "avi",
    "video/x-msvideo":  "avi",
    "video/quicktime":  "mov",
    "video/x-ms-wmv":   "wmv",
}


def _get_extension(content_type: str, original_filename: str) -> str:
    # 1. Map extension safely from verified content_type
    if content_type in CONTENT_TYPE_EXT_MAP:
        return CONTENT_TYPE_EXT_MAP[content_type]
    # 2. Fallback: parse from original filename
    if original_filename and "." in original_filename:
        return original_filename.split(".")[-1].lower()
    return "bin"


def _validate_file_size(file: UploadFile, max_bytes: int, label: str) -> None:
    """
    Reject uploads that exceed *max_bytes*.

    For small limits (≤ 64 MB) we read max+1 bytes in one call — simple and
    fast.  For large limits (videos) we stream in 8 MB chunks to avoid loading
    the entire file into memory at once.
    """
    chunk_size = 8 * 1024 * 1024  # 8 MB
    total_read = 0

    if max_bytes <= 64 * 1024 * 1024:
        # Small file — single read is fine
        data = file.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{label} file too large. Maximum size is "
                       f"{max_bytes // (1024 * 1024)} MB.",
            )
        # Rewind so the caller can read again for writing
        file.file.seek(0)
        return

    # Large file — chunked read to stay memory-safe
    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{label} file too large. Maximum size is "
                       f"{max_bytes // (1024 * 1024 * 1024)} GB.",
            )
    # Rewind so the caller can read again for writing
    file.file.seek(0)


def store_file(file: UploadFile, movie_id: str, asset_category: str, asset_type: str) -> dict:
    if asset_category == "images":
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only JPEG, PNG, or WEBP allowed.",
            )
        _validate_file_size(file, MAX_IMAGE_BYTES, "Image")

    elif asset_category == "videos":
        # Accept any video/* MIME type — FFmpeg handles all common containers
        # (mp4, mkv, avi, mov, webm, wmv …).  Only reject non-video files.
        if not (file.content_type or "").startswith("video/"):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only video files are allowed "
                       "(mp4, mkv, avi, mov, webm).",
            )
        _validate_file_size(file, MAX_VIDEO_BYTES, "Video")

    # ── Shared disk-write logic ─────────────────────────────────────────────
    ext = _get_extension(file.content_type, file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    prefix = asset_type[:-1] if asset_type in ["posters", "backdrops"] else "source"
    new_filename = f"{prefix}_{timestamp}.{ext}"

    folder_path = os.path.join(MEDIA_ROOT, asset_category, asset_type, f"movie_{movie_id}")
    os.makedirs(folder_path, exist_ok=True)

    physical_path = os.path.join(folder_path, new_filename)

    with open(physical_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Store path relative to project root (includes "media/" prefix).
    # normalize_url() in schemas expects "media/images/posters/…" format.
    relative_from_root = physical_path.replace("\\", "/")

    return {
        "public_url": f"/{relative_from_root}",
        "relative_path": relative_from_root,
        "original_filename": file.filename,
    }

