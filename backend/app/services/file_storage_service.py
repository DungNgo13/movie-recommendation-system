import os
import shutil
import logging
from datetime import datetime
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

MEDIA_ROOT = "media"

CONTENT_TYPE_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4"
}

def _get_extension(content_type: str, original_filename: str) -> str:
    # 1. Map extension safely from verified content_type bypassing fake extensions
    if content_type in CONTENT_TYPE_EXT_MAP:
        return CONTENT_TYPE_EXT_MAP[content_type]
    # 2. Fallback cautiously parsing organically.
    if original_filename and "." in original_filename:
        return original_filename.split(".")[-1].lower()
    return "bin"

def store_file(file: UploadFile, movie_id: str, asset_category: str, asset_type: str) -> dict:
    if asset_category == "images":
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        error_msg = "Invalid file type. Only JPEG, PNG, or WEBP allowed."
    elif asset_category == "videos":
        allowed_types = ["video/mp4"]
        error_msg = "Invalid file type. Only MP4 allowed."

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=error_msg)

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
    # normalize_url() in schemas expects a root-relative path like
    # "media/images/posters/...", NOT one relative to the media dir.
    relative_from_root = physical_path.replace("\\", "/")

    return {
        "public_url": f"/{relative_from_root}",
        "relative_path": relative_from_root,
        "original_filename": file.filename
    }
